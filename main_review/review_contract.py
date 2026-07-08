"""Stable request/response contract for Sergeant integrations.

This module is intentionally dependency-light so the CLI, app bridge, IDE adapters,
and tests all speak one shape without importing UI-specific code.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

CONTRACT_VERSION = "sergeant.review.v1"
REVIEW_MODES = {"repository", "pull_request", "changed_files"}
OPTIONAL_V2_REQUEST_FIELDS = {
    "mission_type",
    "branch",
    "commit",
    "pull_request",
    "policy_profile",
    "enterprise_profile",
    "time_budget",
    "execution_permissions",
    "output_preferences",
}


def clean_changed_files(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace("\n", ",").split(",") if part.strip()]
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    raise TypeError("changed_files must be a list, string, or null")


def clean_external_providers(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    raise TypeError("external_providers must be a list of dictionaries or null")


def clean_human_decisions(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    raise TypeError("human_decisions must be a list of dictionaries or null")


def normalize_review_request(request: dict[str, Any]) -> dict[str, Any]:
    """Normalize every caller into Sergeant's one app/API request shape."""
    if not isinstance(request, dict):
        raise TypeError("request must be a dictionary")
    mode = str(request.get("mode") or "repository")
    if mode not in REVIEW_MODES:
        raise ValueError(f"mode must be one of {sorted(REVIEW_MODES)}")
    root = str(request.get("root") or ".")
    normalized = {
        "schema_version": CONTRACT_VERSION,
        "root": root,
        "mode": mode,
        "changed_files": clean_changed_files(request.get("changed_files")),
        "external_review_file": request.get("external_review_file"),
        "external_providers": clean_external_providers(request.get("external_providers")),
        "human_decisions": clean_human_decisions(request.get("human_decisions")),
        "write_learning": bool(request.get("write_learning")),
        "sergeant_benchmark": request.get("sergeant_benchmark"),
        "reference_benchmark": request.get("reference_benchmark"),
        "source": request.get("source") or "app-bridge",
    }
    for field in OPTIONAL_V2_REQUEST_FIELDS:
        if field in request:
            normalized[field] = request.get(field)
    return normalized


def review_status(action: str) -> str:
    if action == "APPROVE":
        return "pass"
    if action == "REQUEST_CHANGES":
        return "block"
    return "needs_work"


def capability_names() -> list[str]:
    return [
        "cross_file",
        "architecture",
        "data_flow",
        "call_graph",
        "security_taint",
        "performance",
        "concurrency",
        "api_contract",
        "test_impact",
        "regression",
        "language",
    ]


def build_review_response(
    *,
    request: dict[str, Any],
    packet: dict[str, Any],
    evidence_consensus: dict[str, Any],
    learning: dict[str, Any],
    graduation: dict[str, Any],
    graduation_markdown: str,
    squad: dict[str, Any],
    v2: dict[str, Any] | None = None,
    markdown: str,
) -> dict[str, Any]:
    """Build the one response format used by CLI, app, IDE, and AI handoff."""
    verdict = packet.get("verdict", {})
    action = str(verdict.get("verdict") or "COMMENT")
    intelligence = packet.get("review_intelligence", {})
    capability_review = packet.get("capability_review", {})
    response = {
        "ok": True,
        "schema_version": CONTRACT_VERSION,
        "service": "Sergeant",
        "request": {
            "root": request.get("root", "."),
            "mode": request.get("mode", "repository"),
            "changed_files": list(request.get("changed_files", [])),
            "source": request.get("source", "app-bridge"),
        },
        "mode": request.get("mode", "repository"),
        "status": review_status(action),
        "action": action,
        "confidence": verdict.get("confidence", 0),
        "reason": verdict.get("reason", ""),
        "required_actions": verdict.get("required_actions", []),
        "quality_score": intelligence.get("quality_score"),
        "root_causes": intelligence.get("root_causes", {}),
        "top_findings": intelligence.get("ranked_findings", [])[:5],
        "capabilities": {
            "status": capability_review.get("capability_status", {}),
            "covered_by_findings": capability_review.get("covered_by_findings", []),
            "findings": capability_review.get("findings", []),
            "expected": capability_names(),
        },
        "evidence_consensus": evidence_consensus,
        "learning": learning,
        "graduation": graduation,
        "graduation_markdown": graduation_markdown,
        "squad": squad,
        "markdown": markdown,
        "packet": packet,
    }
    if v2 is not None:
        response["v2"] = v2
    return response


def github_comments_to_external_provider(live_payload: dict[str, Any]) -> dict[str, Any]:
    """Convert live GitHub comments into an external evidence provider packet."""
    comments = live_payload.get("all_comments", [])
    findings = []
    if isinstance(comments, list):
        for item in comments:
            if not isinstance(item, dict):
                continue
            body = str(item.get("body") or "").strip()
            if not body:
                continue
            findings.append({
                "message": body[:500],
                "evidence": body[:500],
                "path": item.get("path"),
                "author": (item.get("user") or {}).get("login") if isinstance(item.get("user"), dict) else None,
                "source_url": item.get("html_url"),
                "verdict": "COMMENT",
            })
    return {
        "name": "github-live-comments",
        "source": "github-live-comments",
        "verdict": "COMMENT" if findings else "PASS",
        "evidence": findings,
        "findings": findings,
        "metadata": {
            "repository": live_payload.get("repository"),
            "pr_number": live_payload.get("pr_number"),
            "source": live_payload.get("source", "live-github-api"),
        },
    }


def load_review_request_file(path: str | Path) -> dict[str, Any]:
    import json

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("request file must contain a JSON object")
    return payload
