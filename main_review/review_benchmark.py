"""Blind review-quality benchmark for Sergeant.

The benchmark materializes only repository files into a temporary workspace.
Expected findings remain outside that workspace and are loaded only after the
review completes. This prevents existing reviewer comments, fixture prose, and
answer wording from becoming review input.
"""
from __future__ import annotations

import argparse
import json
import os
import sysconfig
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal

from .pr_reviewer import run_independent_pr_review
from .production_hardening import HardeningError, normalize_repository_path

BenchmarkMode = Literal["deterministic", "one-model", "council"]
CASE_SCHEMA = "sergeant.blind-benchmark.case.v1"
RESULT_SCHEMA = "sergeant.blind-benchmark.result.v1"
_ALLOWED_SEVERITIES = {"blocker", "major", "minor"}


class ReviewBenchmarkError(ValueError):
    """Raised when a blind benchmark case or mode is invalid."""


@dataclass(frozen=True)
class FindingMatch:
    expected_id: str
    matched: bool
    score: float
    candidate: dict[str, Any] | None
    category_correct: bool
    severity_correct: bool
    path_correct: bool
    line_correct: bool | None
    root_cause_correct: bool | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BenchmarkCaseResult:
    case_id: str
    title: str
    mode: BenchmarkMode
    expected_verdict: str
    actual_verdict: str
    verdict_correct: bool
    expected_count: int
    prediction_count: int
    true_positive_count: int
    false_positive_count: int
    false_negative_count: int
    precision: float
    recall: float
    f1: float
    severity_accuracy: float | None
    path_accuracy: float | None
    line_accuracy: float | None
    root_cause_accuracy: float | None
    duplicate_rate: float
    finding_completeness: float | None
    duration_ms: float
    cpl_status: str
    model_call_count: int
    distinct_models: list[str]
    matches: list[FindingMatch]
    false_positive_candidates: list[dict[str, Any]]
    missed_expected_findings: list[dict[str, Any]]
    review_packet: dict[str, Any]

    def to_dict(self, *, include_packet: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        payload["matches"] = [match.to_dict() for match in self.matches]
        if not include_packet:
            payload.pop("review_packet", None)
        return payload


def _tokens(value: object) -> set[str]:
    import re

    stop = {"the", "and", "for", "with", "from", "this", "that", "should", "may", "into", "when", "before"}
    return {
        token
        for token in re.findall(r"[a-z0-9_]+", str(value or "").lower())
        if len(token) > 2 and token not in stop
    }


def _normalize_finding(item: dict[str, Any], source: str) -> dict[str, Any] | None:
    severity = str(item.get("severity") or "").lower()
    if severity not in _ALLOWED_SEVERITIES:
        return None
    category = str(item.get("capability") or item.get("category") or "other").lower()
    line_start = item.get("line_start") or item.get("line")
    line_end = item.get("line_end") or line_start
    return {
        "source": source,
        "category": category,
        "severity": severity,
        "message": str(item.get("message") or "").strip(),
        "evidence": str(item.get("evidence") or "").strip(),
        "path": str(item.get("path") or "").strip() or None,
        "line_start": int(line_start) if isinstance(line_start, int) else None,
        "line_end": int(line_end) if isinstance(line_end, int) else None,
        "root_cause": str(item.get("root_cause") or "").strip() or None,
        "why_it_matters": str(item.get("why_it_matters") or "").strip(),
        "trigger": str(item.get("trigger") or "").strip(),
        "consequence": str(item.get("consequence") or "").strip(),
        "safer_alternative": str(item.get("safer_alternative") or "").strip(),
        "verification_test": str(item.get("verification_test") or "").strip(),
        "confidence": float(item.get("confidence") or 0.0),
    }


def _bucket_findings(packet: dict[str, Any], section: str) -> list[dict[str, Any]]:
    payload = packet.get(section, {})
    if not isinstance(payload, dict):
        return []
    findings: list[dict[str, Any]] = []
    for bucket in ("blocking_findings", "major_findings", "minor_findings"):
        rows = payload.get(bucket, [])
        if isinstance(rows, list):
            findings.extend(item for item in rows if isinstance(item, dict))
    return findings


def extract_predictions(packet: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """Extract unique actionable findings and return the raw count for duplicate scoring."""

    raw: list[tuple[str, dict[str, Any]]] = []
    raw.extend(("repository", item) for item in _bucket_findings(packet, "repository_review"))
    raw.extend(("diff", item) for item in _bucket_findings(packet, "diff_review"))
    capability = packet.get("capability_review", {})
    if isinstance(capability, dict):
        raw.extend(("capability", item) for item in capability.get("findings", []) if isinstance(item, dict))
    cpl = packet.get("cpl_review", packet.get("semantic_review", {}))
    if isinstance(cpl, dict):
        raw.extend(("cpl", item) for item in cpl.get("findings", []) if isinstance(item, dict))

    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None, int | None]] = set()
    for source, item in raw:
        finding = _normalize_finding(item, source)
        if finding is None:
            continue
        key = (
            finding["category"],
            finding["message"].lower(),
            finding["path"],
            finding["line_start"],
        )
        if key in seen:
            continue
        seen.add(key)
        normalized.append(finding)
    return normalized, len(raw)


def _path_match(expected_paths: list[str], candidate_path: str | None) -> bool:
    if not expected_paths:
        return True
    return bool(candidate_path and candidate_path in expected_paths)


def _line_match(expected: dict[str, Any], candidate: dict[str, Any]) -> bool | None:
    expected_start = expected.get("line_start")
    expected_end = expected.get("line_end") or expected_start
    if not isinstance(expected_start, int):
        return None
    candidate_start = candidate.get("line_start")
    candidate_end = candidate.get("line_end") or candidate_start
    if not isinstance(candidate_start, int):
        return False
    return candidate_start <= int(expected_end) and int(candidate_end) >= expected_start


def _match_score(expected: dict[str, Any], candidate: dict[str, Any]) -> float:
    expected_category = str(expected.get("category") or "").lower()
    aliases = {expected_category, *[str(item).lower() for item in expected.get("category_aliases", [])]}
    category_score = 1.0 if candidate.get("category") in aliases else 0.0
    expected_paths = [str(item) for item in expected.get("paths", [])]
    path_score = 1.0 if _path_match(expected_paths, candidate.get("path")) else 0.0
    expected_keywords = set(str(item).lower() for item in expected.get("keywords", []))
    candidate_tokens = _tokens(" ".join([candidate.get("message") or "", candidate.get("evidence") or "", candidate.get("root_cause") or ""]))
    keyword_score = len(expected_keywords & candidate_tokens) / max(1, len(expected_keywords))
    severity_score = 1.0 if str(expected.get("severity") or "").lower() == candidate.get("severity") else 0.0
    root = str(expected.get("root_cause") or "")
    root_score = 1.0 if root and root == candidate.get("root_cause") else 0.0
    return round(category_score * 0.28 + path_score * 0.27 + keyword_score * 0.30 + severity_score * 0.10 + root_score * 0.05, 3)


def _greedy_matches(expected: list[dict[str, Any]], predictions: list[dict[str, Any]], threshold: float) -> tuple[list[FindingMatch], set[int]]:
    available = set(range(len(predictions)))
    matches: list[FindingMatch] = []
    used: set[int] = set()
    for expected_item in expected:
        scored = sorted(((_match_score(expected_item, predictions[index]), index) for index in available), reverse=True)
        best_score, best_index = scored[0] if scored else (0.0, -1)
        matched = best_index >= 0 and best_score >= threshold
        candidate = predictions[best_index] if matched else None
        if matched:
            available.remove(best_index)
            used.add(best_index)
        expected_paths = [str(item) for item in expected_item.get("paths", [])]
        expected_root = str(expected_item.get("root_cause") or "")
        matches.append(
            FindingMatch(
                expected_id=str(expected_item.get("id") or "expected"),
                matched=matched,
                score=best_score,
                candidate=candidate,
                category_correct=bool(candidate and candidate.get("category") in {str(expected_item.get("category") or "").lower(), *[str(item).lower() for item in expected_item.get("category_aliases", [])]}),
                severity_correct=bool(candidate and candidate.get("severity") == str(expected_item.get("severity") or "").lower()),
                path_correct=bool(candidate and _path_match(expected_paths, candidate.get("path"))),
                line_correct=_line_match(expected_item, candidate) if candidate else (False if isinstance(expected_item.get("line_start"), int) else None),
                root_cause_correct=(bool(candidate and candidate.get("root_cause") == expected_root) if expected_root else None),
            )
        )
    return matches, used
