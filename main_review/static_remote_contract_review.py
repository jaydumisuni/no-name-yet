"""Static review for remote response contract violations hidden as empty data."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_DART_SUFFIXES = {".dart"}
_REMOTE_ASSIGNMENT_RE = re.compile(
    r"\b(?:final|var)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*await\s+"
    r"(?P<call>[^;\n]*(?:_apiClient|apiClient|http|client|dio)[^;\n]*\.(?:get|fetch|request)\s*\([^;]*\))\s*;",
    re.I,
)


def _safe_text(root: Path, relative: str) -> str:
    try:
        resolved_root = root.resolve()
        path = (resolved_root / relative).resolve()
        if not path.is_relative_to(resolved_root) or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _line(text: str, offset: int) -> int:
    return text[: max(0, offset)].count("\n") + 1


def _empty_list_guard(variable: str) -> re.Pattern[str]:
    escaped = re.escape(variable)
    return re.compile(
        rf"\bif\s*\(\s*{escaped}\s+is!\s+List(?:\s*<[^>]+>)?\s*\)\s*"
        rf"(?:\{{\s*)?return\s+(?:const\s+)?(?:<[^>]+>\s*)?\[\]\s*;",
        re.I | re.S,
    )


def _finding(path: str, line_start: int, variable: str) -> dict[str, Any]:
    return {
        "source": "static-remote-contract-officer",
        "officer": "Engineer",
        "capability": "api_contract",
        "category": "api_contract",
        "severity": "major",
        "root_cause": "remote-collection-contract-violation-collapsed-to-empty",
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": f"{path}:{line_start}",
        "supporting_evidence_refs": [f"{path}:{line_start}"],
        "message": "A malformed remote collection response is converted into a valid empty result.",
        "evidence": (
            f"The remote response stored in `{variable}` is required to be a List, but the mismatch branch returns an empty list. "
            "Callers therefore cannot distinguish a real empty collection from a broken endpoint, incompatible schema, or proxy error payload."
        ),
        "falsifiers_checked": [
            "Checked that the value originates from an awaited HTTP/API client call.",
            "Checked that the mismatch is a remote response-shape violation rather than an optional local cache miss.",
            "Checked that the mismatch branch returns empty data instead of raising or returning an explicit error result.",
        ],
        "verification_test": (
            "Raise or return an explicit contract error for non-list responses, preserve genuine empty lists unchanged, and test both the empty-success "
            "and malformed-response cases."
        ),
        "confidence": 0.98,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def run_static_remote_contract_review(
    root: str | Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    readable: list[str] = []
    findings: list[dict[str, Any]] = []

    for path in changed:
        if Path(path).suffix.lower() not in _DART_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        for assignment in _REMOTE_ASSIGNMENT_RE.finditer(text):
            variable = assignment.group("name")
            window = text[assignment.end() : assignment.end() + 1200]
            guard = _empty_list_guard(variable).search(window)
            if guard is None:
                continue
            line_start = _line(text, assignment.end() + guard.start())
            findings.append(_finding(path, line_start, variable))
            break

    return {
        "schema_version": "sergeant.static-remote-contract-review.v1",
        "mode": "model_free_static",
        "finding_count": len(findings),
        "findings": findings,
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
