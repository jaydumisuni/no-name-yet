"""Public safety boundary checks for Sergeant.

Sergeant is a reviewer. It may inspect repository-contained files and read
explicitly trusted public API data, but it must not become a patch writer,
write-token client, or unsafe execution engine.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .production_hardening import HardeningError, normalize_repository_path

FORBIDDEN_ACTIONS = {
    "edit_code",
    "write_patch",
    "apply_patch",
    "execute_pr_code",
    "run_untrusted_code",
    "shell_from_pr",
    "use_write_token",
    "change_policy",
    "disable_sandbox",
    "export_private_memory",
}
ALLOWED_ACTIONS = {
    "scan",
    "review",
    "diff_review",
    "collect_comments",
    "live_fetch_read_only",
    "ingest_external_evidence",
    "learn_verified_outcome",
}


def check_action_boundary(action: str, context: dict[str, Any] | None = None) -> dict[str, object]:
    """Evaluate an action using a fail-closed public reviewer boundary."""

    context = context or {}
    normalized = str(action or "").strip().lower().replace("-", "_").replace(" ", "_")
    if context.get("requires_write_token"):
        return {"allowed": False, "action": normalized, "reason": "Write-token actions are outside Sergeant's reviewer boundary."}
    if context.get("executes_untrusted_code"):
        return {"allowed": False, "action": normalized, "reason": "Executing untrusted pull-request code is outside Sergeant's reviewer boundary."}
    if context.get("requires_shell"):
        return {"allowed": False, "action": normalized, "reason": "Shell execution requested by review input is outside Sergeant's public boundary."}
    if context.get("exports_private_data"):
        return {"allowed": False, "action": normalized, "reason": "Private project evidence cannot cross Sergeant's public boundary."}
    if normalized in FORBIDDEN_ACTIONS:
        return {"allowed": False, "action": normalized, "reason": "Sergeant reviews evidence but does not edit code, execute PR-controlled code, alter policy, export private memory, or use write tokens."}
    if normalized in ALLOWED_ACTIONS:
        return {"allowed": True, "action": normalized, "reason": "Read-only review action within Sergeant's public safety boundary."}
    return {"allowed": False, "action": normalized, "reason": "Unknown actions are denied until explicitly added to Sergeant's public boundary."}


def repository_visibility_policy(is_public: bool = True) -> dict[str, object]:
    """Describe the enforced public/private product split."""

    if is_public:
        return {
            "visibility": "public-open-source",
            "keep_public": ["review engine", "app bridge", "static analysis", "evidence consensus", "learning framework", "squad orchestration"],
            "keep_private": ["THETECHGUY/Hunter private project rules", "private repo memory", "write-token bot deployment", "customer/client evidence", "internal operational secrets"],
            "default_action_policy": "deny-unknown",
        }
    return {"visibility": "private", "keep_private": ["all project-specific evidence and deployment secrets"]}


def assert_safe_path(root: str | Path, path: str | Path) -> dict[str, object]:
    """Return a structured sandbox decision for a repository-relative path."""

    try:
        relative = normalize_repository_path(root, path)
    except HardeningError as error:
        root_path = Path(root).resolve()
        raw = Path(str(path))
        target = raw.resolve() if raw.is_absolute() else (root_path / raw).resolve()
        return {"allowed": False, "reason": str(error), "path": str(target)}
    target = (Path(root).resolve() / relative).resolve()
    return {"allowed": True, "reason": "Path stays inside repository root.", "path": str(target), "relative_path": relative}
