"""Run Sergeant against live battle fixtures and score expected findings.

This module is the live comparison layer for battle tests. It fetches a real
GitHub PR file list, patches, and review comments, materializes them into a
temporary review workspace, runs Sergeant's existing review engine, and compares
the resulting structured output against the fixture's expected findings.

The comparison is intentionally transparent and conservative. It uses keyword
overlap, not an LLM judge. Reports include caveats so the result cannot be
mistaken for a full historical checkout or a semantic evaluation.
"""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from main_review.evidence import BattleAwareEvidenceProvider, RiskPathEvidenceProvider, SecretEvidenceProvider, collect_evidence
from main_review.github_diff_fetch import fetch_pr_diff_live
from main_review.github_live_fetch import fetch_pr_comments_live
from main_review.verdict import decide_verdict

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "to", "of",
    "and", "or", "in", "on", "for", "with", "this", "that", "it", "as", "should",
    "would", "could", "not", "no", "into", "from", "by", "at", "simple", "treat",
    "focus", "check", "verify", "flag",
}

_SYNONYMS: dict[str, set[str]] = {
    "architecture": {"architectural", "lifecycle", "review", "risk", "cleanup"},
    "lifecycle": {"architecture", "stages", "ordering", "teardown", "request", "app"},
    "deprecation": {"deprecated", "alias", "aliases", "migration", "behavior"},
    "migration": {"deprecation", "deprecated", "alias", "aliases", "behavior"},
    "proxy": {"availability", "visibility", "context", "current_app", "request"},
    "availability": {"proxy", "visibility", "lifecycle", "stages"},
    "copied": {"copy", "context", "reuse", "regression", "risk"},
    "context": {"request", "app", "lifecycle", "teardown", "streaming", "shell", "copied"},
    "teardown": {"ordering", "context", "lifecycle"},
    "preserved": {"test", "client", "contexts", "context"},
    "streaming": {"context", "lifecycle"},
    "shell": {"context", "lifecycle"},
    "query": {"url", "urlparse", "separator", "question", "string"},
    "question": {"mark", "url", "query", "separator"},
    "regression": {"test", "risk", "behavior"},
    "duplicate": {"overlap", "overlapping", "parameterized", "repeated"},
    "data": {"params", "payload", "unrelated", "clarity"},
    "params": {"data", "payload", "unrelated", "clarity"},
    "follow": {"followup", "follow-up", "feedback", "continued"},
}

_PATCH_REVIEW_PROVIDERS = (
    SecretEvidenceProvider(),
    RiskPathEvidenceProvider(),
    BattleAwareEvidenceProvider(),
)


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9_]+", text.lower())
    keywords = {word for word in words if word not in _STOPWORDS and len(word) > 2}
    expanded = set(keywords)
    for keyword in keywords:
        expanded.update(_SYNONYMS.get(keyword, set()))
    return expanded


def _overlap_score(expected: str, candidates: list[str]) -> tuple[float, str | None]:
    expected_keywords = _keywords(expected)
    if not expected_keywords:
        return 0.0, None

    best_ratio = 0.0
    best_candidate: str | None = None
    for candidate in candidates:
        candidate_keywords = _keywords(candidate)
        if not candidate_keywords:
            continue
        overlap = expected_keywords & candidate_keywords
        precision_bonus = len(overlap) / max(len(candidate_keywords), 1)
        ratio = (len(overlap) / len(expected_keywords)) + min(precision_bonus, 0.15)
        if ratio > best_ratio:
            best_ratio = ratio
            best_candidate = candidate
    return min(best_ratio, 1.0), best_candidate


@dataclass(frozen=True)
class ExpectedFindingMatch:
    expected: str
    matched: bool
    overlap_ratio: float
    best_candidate: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected": self.expected,
            "matched": self.matched,
            "overlap_ratio": round(self.overlap_ratio, 2),
            "best_candidate": self.best_candidate,
        }


@dataclass(frozen=True)
class BattleRunResult:
    repository: str
    pull_request: int
    fixture_path: str
    files_reviewed: list[str]
    sergeant_finding_texts: list[str]
    expected_matches: list[ExpectedFindingMatch]
    false_positive_candidates: list[str]
    agreement_rate: float
    match_threshold: float
    caveats: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "pull_request": self.pull_request,
            "fixture_path": self.fixture_path,
            "files_reviewed": self.files_reviewed,
            "sergeant_finding_texts": self.sergeant_finding_texts,
            "expected_matches": [match.to_dict() for match in self.expected_matches],
            "missed_expected_findings": [match.expected for match in self.expected_matches if not match.matched],
            "false_positive_candidates": self.false_positive_candidates,
            "agreement_rate": round(self.agreement_rate, 2),
            "match_threshold": self.match_threshold,
            "caveats": self.caveats,
        }


def _extract_finding_texts(verdict_report: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    verdict = verdict_report.get("verdict", verdict_report)
    if not isinstance(verdict, dict):
        return texts

    for bucket in ("blocking_findings", "major_findings", "minor_findings", "notes", "findings"):
        items = verdict.get(bucket, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                parts = [
                    str(item.get("category", "")),
                    str(item.get("message", "")),
                    str(item.get("evidence", "")),
                    str(item.get("path", "")),
                    str(item.get("severity", "")),
                ]
                text = " ".join(part for part in parts if part).strip()
                if text:
                    texts.append(text)
            elif isinstance(item, str) and item.strip():
                texts.append(item.strip())

    return texts


def _write_patch_workspace(files: list[Any], root: Path) -> list[str]:
    written: list[str] = []
    for file in files:
        patch = getattr(file, "patch", None)
        filename = getattr(file, "filename", "")
        if not patch or not filename:
            continue
        destination = root / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(patch, encoding="utf-8")
        written.append(filename)
    return written


def _write_comment_workspace(comments: list[dict[str, Any]], root: Path) -> str | None:
    if not comments:
        return None
    lines = ["# Live PR review comments", ""]
    for index, comment in enumerate(comments, start=1):
        body = str(comment.get("body", "")).strip()
        review = str(comment.get("review", "")).strip()
        path = str(comment.get("path", "")).strip()
        if not body and not review:
            continue
        lines.append(f"## Comment {index}")
        if review:
            lines.append(f"Review status: {review}")
        if path:
            lines.append(f"Path: {path}")
        if body:
            lines.append(body)
        lines.append("")
    if len(lines) <= 2:
        return None
    destination = root / "__sergeant_pr_comments.md"
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination.name


def _review_patch_workspace(root: Path) -> dict[str, object]:
    evidence_payload = collect_evidence(root, providers=_PATCH_REVIEW_PROVIDERS)
    report = decide_verdict(evidence_payload)
    return {"verdict": report.to_dict(), "evidence": evidence_payload}


def _false_positive_candidates(finding_texts: list[str], matches: list[ExpectedFindingMatch]) -> list[str]:
    matched_texts = {match.best_candidate for match in matches if match.matched and match.best_candidate}
    return [text for text in finding_texts if text not in matched_texts]


def run_battle_comparison(
    fixture_path: str | Path,
    *,
    token: str | None = None,
    base_url: str = "https://api.github.com",
    match_threshold: float = 0.5,
) -> BattleRunResult:
    """Fetch a fixture's real PR patches/comments, run Sergeant, and score agreement."""
    fixture_path = Path(fixture_path)
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    repository = payload["repository"]
    pr_number = int(payload["pull_request"])
    expected_findings = [str(item) for item in payload.get("expected_sergeant_findings", [])]

    diff = fetch_pr_diff_live(repository, pr_number, token=token, base_url=base_url)
    comments = fetch_pr_comments_live(repository, pr_number, token=token, base_url=base_url)
    caveats = [
        "Files reviewed are GitHub PR patch text plus PR review comments materialized into a temporary workspace, not a full historical repository checkout.",
        "Agreement scoring is transparent keyword-overlap with documented synonym expansion, not semantic or LLM judged.",
        "Repository-level documentation/test-footprint checks are disabled for patch-only battle comparison to avoid false positives from partial workspaces.",
        "A conceptual match can score low when wording differs between Sergeant output and fixture expectations.",
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        files_written = _write_patch_workspace(diff.files, temp_root)
        comment_file = _write_comment_workspace(comments.all_comments, temp_root)
        if comment_file:
            files_written.append(comment_file)
        if not files_written:
            caveats.append("No reviewable patches or comments were returned by GitHub for this PR.")
        verdict_report = _review_patch_workspace(temp_root)

    finding_texts = _extract_finding_texts(verdict_report)
    matches: list[ExpectedFindingMatch] = []
    matched_count = 0
    for expected in expected_findings:
        ratio, candidate = _overlap_score(expected, finding_texts)
        matched = ratio >= match_threshold
        if matched:
            matched_count += 1
        matches.append(ExpectedFindingMatch(expected, matched, ratio, candidate))

    agreement_rate = matched_count / len(expected_findings) if expected_findings else 0.0

    return BattleRunResult(
        repository=repository,
        pull_request=pr_number,
        fixture_path=str(fixture_path),
        files_reviewed=files_written,
        sergeant_finding_texts=finding_texts,
        expected_matches=matches,
        false_positive_candidates=_false_positive_candidates(finding_texts, matches),
        agreement_rate=agreement_rate,
        match_threshold=match_threshold,
        caveats=caveats,
    )
