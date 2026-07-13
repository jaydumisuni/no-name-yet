"""Select repository files for semantic review when no Git diff is supplied."""

from __future__ import annotations

from pathlib import Path

from .scanner import scan_repository

ROLE_PRIORITY = {
    "infrastructure": 0,
    "config": 1,
    "database": 2,
    "source": 3,
    "ui": 4,
    "test": 5,
    "manifest": 6,
    "documentation": 7,
}


def semantic_review_files(root: str | Path, changed_files: list[str], *, limit: int = 40) -> list[str]:
    """Return explicit changed files or a bounded, risk-first workspace sample."""

    explicit = list(dict.fromkeys(path.strip() for path in changed_files if path.strip()))
    if explicit:
        return explicit

    insight = scan_repository(root)
    candidates = [
        file
        for file in insight.files
        if file.role in ROLE_PRIORITY and file.language not in {"Binary", "Unknown"}
    ]
    candidates.sort(
        key=lambda file: (
            0 if file.high_risk else 1,
            ROLE_PRIORITY.get(file.role, 99),
            file.path,
        )
    )
    return [file.path for file in candidates[: max(1, limit)]]
