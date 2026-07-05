"""GitHub bot payload helpers for Main Review.

The real GitHub posting step can be handled by GitHub Actions or a service
wrapper. This module builds the comment/review payload from Main Review's own
independent PR review result.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .pr_reviewer import render_pr_review_markdown, run_independent_pr_review


def build_github_review_payload(
    root: str | Path = ".",
    *,
    changed_files: list[str] | None = None,
    external_review_file: str | Path | None = None,
) -> dict[str, Any]:
    packet = run_independent_pr_review(
        root,
        changed_files=changed_files or [],
        external_review_file=external_review_file,
    )
    verdict = packet.get("verdict", {})
    action = str(verdict.get("verdict", "COMMENT"))
    if action not in {"APPROVE", "COMMENT", "REQUEST_CHANGES"}:
        action = "COMMENT"
    return {
        "action": action,
        "body": render_pr_review_markdown(packet),
        "packet": packet,
    }


def write_github_review_payload(
    output_path: str | Path,
    root: str | Path = ".",
    *,
    changed_files: list[str] | None = None,
    external_review_file: str | Path | None = None,
) -> dict[str, Any]:
    import json

    payload = build_github_review_payload(
        root,
        changed_files=changed_files,
        external_review_file=external_review_file,
    )
    path = Path(output_path)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
