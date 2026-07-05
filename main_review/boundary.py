"""Public safety boundary checks for Sergeant.

Sergeant is a reviewer. It may inspect files and read public API data, but it
must not become a patch writer or an unsafe execution engine.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

FORBIDDEN_ACTIONS = {"edit_code", "write_patch", "apply_patch", "execute_pr_code", "run_untrusted_code", "shell_from_pr", "use_write_token"}
ALLOWED_ACTIONS = {"scan", "review", "diff_review", "collect_comments", "live_fetch_read_only", "ingest_external_evidence", "learn_verified_outcome"}


def check_action_boundary(action: str, context: dict[str, Any] | None = None) -> dict[str, object]:
    context = context or {}
    normalized = str(action or "").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in FORBIDDEN_ACTIONS:
        return {"allowed": False, "action": normalized, "reason": "Sergeant reviews evidence but does not edit code, execute PR-controlled code, or use write tokens."}
    if normalized in ALLOWED_ACTIONS:
        return {"allowed": True, "action": normalized, "reason": "Read-only review action within Sergeant's public safety boundary."}
    if context.get("requires_write_token"):
        return {"allowed": False, "action": normalized, "reason": "Write-token actions are outside Sergeant's reviewer boundary."}
    if context.get("executes_untrusted_code"):
        return {"allowed": False, "action": normalized, "reason": "Executing untrusted pull-request code is outside Sergeant's reviewer boundary."}
    return {"allowed": True, "action": normalized, "reason": "No boundary violation detected."}


def repository_visibility_policy(is_public: bool = True) -> dict[str, object]:
    if is_public:
        return {
            "visibility": "public-open-source",
            "keep_public": ["review engine", "app bridge", "static analysis", "evidence consensus", "learning framework", "squad orchestration"],
            "keep_private": ["THETECHGUY/Hunter private project rules", "private repo memory", "write-token bot deployment", "customer/client evidence", "internal operational secrets"],
        }
    return {"visibility": "private", "keep_private": ["all project-specific evidence and deployment secrets"]}


def assert_safe_path(root: str | Path, path: str | Path) -> dict[str, object]:
    root_path = Path(root).resolve()
    target = (root_path / path).resolve()
    try:
        target.relative_to(root_path)
    except ValueError:
        return {"allowed": False, "reason": "Path escapes repository root.", "path": str(target)}
    return {"allowed": True, "reason": "Path stays inside repository root.", "path": str(target)}
