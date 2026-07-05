"""App bridge for Sergeant.

This is the stable integration layer an app can call without knowing Sergeant's
internal module layout. It accepts a JSON-like request, runs the review pipeline,
and returns a compact response suitable for UI cards, API responses, or logs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .evidence_consensus import build_evidence_consensus
from .learning_loop import run_learning_loop
from .pr_reviewer import render_pr_review_markdown, run_independent_pr_review


REVIEW_MODES = {"repository", "pull_request", "changed_files"}


def _clean_changed_files(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace("\n", ",").split(",") if part.strip()]
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    raise TypeError("changed_files must be a list, string, or null")


def _clean_external_providers(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    raise TypeError("external_providers must be a list of dictionaries or null")


def _clean_human_decisions(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    raise TypeError("human_decisions must be a list of dictionaries or null")


def _review_status(action: str) -> str:
    if action == "APPROVE":
        return "pass"
    if action == "REQUEST_CHANGES":
        return "block"
    return "needs_work"


def handle_app_review_request(request: dict[str, Any]) -> dict[str, Any]:
    """Run a Sergeant review from an app-facing request payload."""

    if not isinstance(request, dict):
        raise TypeError("request must be a dictionary")
    mode = str(request.get("mode") or "repository")
    if mode not in REVIEW_MODES:
        raise ValueError(f"mode must be one of {sorted(REVIEW_MODES)}")

    root = Path(str(request.get("root") or "."))
    changed_files = _clean_changed_files(request.get("changed_files"))
    external_review_file = request.get("external_review_file")
    external_providers = _clean_external_providers(request.get("external_providers"))
    human_decisions = _clean_human_decisions(request.get("human_decisions"))
    write_learning = bool(request.get("write_learning"))
    packet = run_independent_pr_review(
        root,
        changed_files=changed_files,
        external_review_file=Path(str(external_review_file)) if external_review_file else None,
    )
    evidence_consensus = build_evidence_consensus(packet, external_providers)
    learning = run_learning_loop(root, evidence_consensus, human_decisions, write=write_learning) if human_decisions else {"learning": {"candidates": [], "ignored": [], "candidate_count": 0}, "written": {"written_count": 0, "records": []}}
    verdict = packet.get("verdict", {})
    action = str(verdict.get("verdict") or "COMMENT")
    intelligence = packet.get("review_intelligence", {})
    return {
        "ok": True,
        "service": "Sergeant",
        "mode": mode,
        "status": _review_status(action),
        "action": action,
        "confidence": verdict.get("confidence", 0),
        "reason": verdict.get("reason", ""),
        "required_actions": verdict.get("required_actions", []),
        "quality_score": intelligence.get("quality_score"),
        "root_causes": intelligence.get("root_causes", {}),
        "top_findings": intelligence.get("ranked_findings", [])[:5],
        "evidence_consensus": evidence_consensus,
        "learning": learning,
        "markdown": render_pr_review_markdown(packet),
        "packet": packet,
    }
