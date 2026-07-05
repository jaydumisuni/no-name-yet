"""Tier 4 verified learning loop for Sergeant.

Tier 4 converts human decisions on review findings into verified engineering
memory. Sergeant learns only from outcomes that are explicitly accepted,
rejected, or marked as lessons; it does not blindly memorize every finding.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .memory import ReviewMemoryStore, default_memory_path, new_memory_record

ACCEPTED = {"accepted", "correct", "fixed", "true_positive"}
REJECTED = {"rejected", "false_positive", "intentional", "wontfix"}
LESSON = {"learn", "lesson", "pattern"}


def _text(value: object) -> str:
    return str(value or "").strip()


def _decision_status(value: object) -> str:
    raw = _text(value).lower().replace(" ", "_").replace("-", "_")
    if raw in ACCEPTED:
        return "accepted"
    if raw in REJECTED:
        return "rejected"
    if raw in LESSON:
        return "lesson"
    return "pending"


def _title(finding: dict[str, Any], decision: str) -> str:
    message = _text(finding.get("message")) or "Review finding"
    return f"{decision.title()}: {message[:96]}"


def _tags(finding: dict[str, Any], decision: str) -> list[str]:
    tags = ["sergeant", "review-learning", decision]
    for key in ["classification", "category", "capability", "root_cause", "severity"]:
        value = _text(finding.get(key))
        if value:
            tags.append(value.lower().replace(" ", "-"))
    return sorted(set(tags))


def _applies_to(finding: dict[str, Any]) -> list[str]:
    paths = []
    path = _text(finding.get("path"))
    if path:
        paths.append(path)
    for item in finding.get("related_paths", []) if isinstance(finding.get("related_paths"), list) else []:
        if _text(item):
            paths.append(_text(item))
    return sorted(set(paths))


def build_learning_candidates(review_result: dict[str, Any], human_decisions: list[dict[str, Any]]) -> dict[str, Any]:
    """Build memory candidates from human-confirmed review outcomes."""
    findings = review_result.get("classified_findings") or review_result.get("ranked_findings") or []
    by_index = {str(index): finding for index, finding in enumerate(findings) if isinstance(finding, dict)}
    by_message = {_text(finding.get("message")): finding for finding in findings if isinstance(finding, dict)}
    candidates: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []

    for decision in human_decisions:
        status = _decision_status(decision.get("decision"))
        target = _text(decision.get("finding_index"))
        message = _text(decision.get("message"))
        finding = by_index.get(target) or by_message.get(message)
        if not finding or status == "pending":
            ignored.append({"decision": decision, "reason": "no matched finding or no verified outcome"})
            continue
        memory_status = "verified" if status in {"accepted", "lesson"} else "rejected"
        kind = "lesson" if status == "lesson" else "risk"
        reason = _text(decision.get("reason")) or _text(finding.get("evidence")) or "Human review outcome recorded."
        candidates.append({
            "kind": kind,
            "title": _title(finding, status),
            "summary": _text(finding.get("message")),
            "reason": reason,
            "status": memory_status,
            "scope": _text(decision.get("scope")) or "repository",
            "evidence": [item for item in [_text(finding.get("evidence")), _text(decision.get("evidence"))] if item],
            "tags": _tags(finding, status),
            "applies_to": _applies_to(finding),
            "confidence": float(decision.get("confidence") or finding.get("confidence") or 0.7),
        })
    return {"candidates": candidates, "ignored": ignored, "candidate_count": len(candidates)}


def apply_learning_candidates(root: str | Path, learning_packet: dict[str, Any]) -> dict[str, Any]:
    store = ReviewMemoryStore(default_memory_path(root))
    written = []
    for candidate in learning_packet.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        record = new_memory_record(
            kind=candidate.get("kind", "lesson"),
            title=candidate.get("title", "Review learning"),
            summary=candidate.get("summary", ""),
            reason=candidate.get("reason", ""),
            status=candidate.get("status", "verified"),
            scope=candidate.get("scope", "repository"),
            evidence=candidate.get("evidence", []),
            tags=candidate.get("tags", []),
            applies_to=candidate.get("applies_to", []),
            confidence=candidate.get("confidence", 0.7),
        )
        store.add(record)
        written.append(record.__dict__)
    return {"written_count": len(written), "records": written}


def run_learning_loop(root: str | Path, review_result: dict[str, Any], human_decisions: list[dict[str, Any]], *, write: bool = False) -> dict[str, Any]:
    candidates = build_learning_candidates(review_result, human_decisions)
    result = {"learning": candidates, "written": {"written_count": 0, "records": []}}
    if write:
        result["written"] = apply_learning_candidates(root, candidates)
    return result
