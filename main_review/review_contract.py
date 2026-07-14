"""Stable, production-hardened request/response contract for Sergeant.

The CLI, App Bridge, IDE adapters, and AI handoff all cross this boundary. Input
is normalized, path-contained, permission-checked, and bounded before review.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .production_hardening import (
    enforce_mission_permissions,
    normalize_changed_files,
    normalize_input_file,
    normalize_time_budget,
)

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
        providers = [item for item in value if isinstance(item, dict)]
        if len(providers) > 50:
            raise ValueError("external_providers exceeds the safety limit of 50 providers")
        return providers
    raise TypeError("external_providers must be a list of dictionaries or null")


def clean_human_decisions(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        decisions = [item for item in value if isinstance(item, dict)]
        if len(decisions) > 500:
            raise ValueError("human_decisions exceeds the safety limit of 500 decisions")
        return decisions
    raise TypeError("human_decisions must be a list of dictionaries or null")


def _optional_dict(request: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = request.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError(f"{key} must be a dictionary or null")
    return value


def normalize_review_request(request: dict[str, Any]) -> dict[str, Any]:
    """Normalize every caller into Sergeant's one fail-closed request shape."""

    if not isinstance(request, dict):
        raise TypeError("request must be a dictionary")
    mode = str(request.get("mode") or "repository")
    if mode not in REVIEW_MODES:
        raise ValueError(f"mode must be one of {sorted(REVIEW_MODES)}")
    root_path = Path(str(request.get("root") or ".")).resolve()
    profile = str(request.get("policy_profile") or "default").strip().lower()
    changed_files = normalize_changed_files(root_path, clean_changed_files(request.get("changed_files")))
    permissions = enforce_mission_permissions(profile, _optional_dict(request, "execution_permissions"))
    time_budget = normalize_time_budget(_optional_dict(request, "time_budget"))
    external_review_file = request.get("external_review_file")
    safe_external_review_file = normalize_input_file(root_path, external_review_file) if external_review_file else None

    normalized = {
        "schema_version": CONTRACT_VERSION,
        "root": str(root_path),
        "mode": mode,
        "changed_files": changed_files,
        "external_review_file": safe_external_review_file,
        "external_providers": clean_external_providers(request.get("external_providers")),
        "human_decisions": clean_human_decisions(request.get("human_decisions")),
        "write_learning": bool(request.get("write_learning")),
        "sergeant_benchmark": request.get("sergeant_benchmark"),
        "reference_benchmark": request.get("reference_benchmark"),
        "source": str(request.get("source") or "app-bridge")[:200],
        "policy_profile": profile,
        "time_budget": time_budget,
        "execution_permissions": permissions,
    }
    for field in OPTIONAL_V2_REQUEST_FIELDS - {"policy_profile", "time_budget", "execution_permissions"}:
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
            "policy_profile": request.get("policy_profile", "default"),
            "execution_permissions": request.get("execution_permissions", {}),
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
    """Convert validated live GitHub comments into an evidence-provider packet."""

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
            "pull_request": live_payload.get("pull_request", {}),
            "token_scope_assessment": live_payload.get("token_scope_assessment", {}),
        },
    }


def load_review_request_file(path: str | Path) -> dict[str, Any]:
    import json

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("request file must contain a JSON object")
    return payload
