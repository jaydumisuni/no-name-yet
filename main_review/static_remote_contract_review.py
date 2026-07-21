"""Static review for remote and cross-layer contract violations."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from .static_protocol_lifecycle_review import run_static_protocol_lifecycle_review
from .static_transfer_21_review import run_static_transfer_21_review
from .static_transfer_22_review import run_static_transfer_22_review
from .static_transfer_23_review import run_static_transfer_23_review
from .static_transfer_24_review import run_static_transfer_24_review
from .static_transfer_25_review import run_static_transfer_25_review
from .static_transfer_26_review import run_static_transfer_26_review
from .static_transfer_27_review import run_static_transfer_27_review
from .static_transfer_28_review import run_static_transfer_28_review
from .static_transfer_29_review import run_static_transfer_29_review
from .static_transfer_30_review import run_static_transfer_30_review


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


def run_static_remote_contract_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
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
            findings.append(_finding(path, _line(text, assignment.end() + guard.start()), variable))
            break

    protocol_lifecycle = run_static_protocol_lifecycle_review(root_path, changed)
    transfer_21 = run_static_transfer_21_review(root_path, changed)
    transfer_22 = run_static_transfer_22_review(root_path, changed)
    transfer_23 = run_static_transfer_23_review(root_path, changed)
    transfer_24 = run_static_transfer_24_review(root_path, changed)
    transfer_25 = run_static_transfer_25_review(root_path, changed)
    transfer_26 = run_static_transfer_26_review(root_path, changed)
    transfer_27 = run_static_transfer_27_review(root_path, changed)
    transfer_28 = run_static_transfer_28_review(root_path, changed)
    transfer_29 = run_static_transfer_29_review(root_path, changed)
    transfer_30 = run_static_transfer_30_review(root_path, changed)
    for result in (
        protocol_lifecycle,
        transfer_21,
        transfer_22,
        transfer_23,
        transfer_24,
        transfer_25,
        transfer_26,
        transfer_27,
        transfer_28,
        transfer_29,
        transfer_30,
    ):
        findings.extend(dict(item) for item in result.get("findings", []) if isinstance(item, dict))

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding.get("root_cause")), str(finding.get("path")), int(finding.get("line_start") or 0))] = finding

    return {
        "schema_version": "sergeant.static-remote-contract-review.v10",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "static_transfer_21_review": transfer_21,
        "static_transfer_22_review": transfer_22,
        "static_transfer_23_review": transfer_23,
        "static_transfer_24_review": transfer_24,
        "static_transfer_25_review": transfer_25,
        "static_transfer_26_review": transfer_26,
        "static_transfer_27_review": transfer_27,
        "static_transfer_28_review": transfer_28,
        "static_transfer_29_review": transfer_29,
        "static_transfer_30_review": transfer_30,
        "executed_project_code": False,
    }
