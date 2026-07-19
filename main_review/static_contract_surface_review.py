"""Canonical transfer-10 contract surface review.

This wrapper reuses the proven UI-persistence and C++ authority analyzers from
``static_transfer_10_review`` while leaving remote collection-shape ownership to
the older, independently tested ``static_remote_contract_review`` officer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .static_transfer_10_review import (
    _SOURCE_SUFFIXES,
    _global_authority_findings,
    _safe_text,
    _ui_state_only_save_findings,
)


def run_static_contract_surface_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    texts: dict[str, str] = {}
    readable: list[str] = []
    findings: list[dict[str, Any]] = []

    for path in changed:
        if Path(path).suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        texts[path] = text
        readable.append(path)
        findings.extend(_ui_state_only_save_findings(path, text))

    findings.extend(_global_authority_findings(changed, texts))

    unique = {(str(item["root_cause"]), str(item["path"])): item for item in findings}
    return {
        "schema_version": "sergeant.static-contract-surface-review.v3",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
