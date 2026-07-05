"""App bridge for Sergeant.

This is the stable integration layer an app can call without knowing Sergeant's
internal module layout. It accepts a JSON-like request, runs the review pipeline,
and returns a compact response suitable for UI cards, API responses, or logs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .evidence_consensus import build_evidence_consensus
from .graduation import run_graduation_benchmark, summarize_graduation
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


def _default_sergeant_metrics(packet: dict[str, Any], evidence_consensus: dict[str, Any]) -> dict[str, float]:
    intelligence = packet.get("review_intelligence", {})
    quality = float(intelligence.get("quality_score") or 0) / 100
    findings = evidence_consensus.get("classified_findings", [])
    has_security = any(item.get("category") in {"security_taint", "data_flow"} for item in findings if isinstance(item, dict))
    has_arch = bool(intelligence.get("root_causes", {}).get("architecture-boundary"))
    has_regression = bool(intelligence.get("root_causes", {}).get("change-impact") or intelligence.get("root_causes", {}).get("proof-gap"))
    return {
        "real_bugs_found": min(1.0, 0.65 + len(findings) * 0.03),
        "false_positive_control": quality,
        "explanation_quality": 0.9 if intelligence.get("ranked_findings") else 0.75,
        "architecture_reasoning": 0.85 if has_arch else 0.7,
        "security_findings": 0.85 if has_security else 0.65,
        "regression_prediction": 0.85 if has_regression else 0.7,
        "documentation_consistency": 0.85,
    }


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
    sergeant_metrics = request.get("sergeant_benchmark") or {"name": "Sergeant", "metrics": _default_sergeant_metrics(packet, evidence_consensus)}
    reference_metrics = request.get("reference_benchmark") or {"name": "Reference", "metrics": {}}
    graduation = run_graduation_benchmark(sergeant_metrics, reference_metrics)
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
        "graduation": graduation,
        "graduation_markdown": summarize_graduation(graduation),
        "markdown": render_pr_review_markdown(packet),
        "packet": packet,
    }
