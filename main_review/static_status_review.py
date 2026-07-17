"""Static ownership analysis for shared status-subresource writers."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .static_recovery_review import run_static_recovery_review
from .static_stale_state_review import run_static_stale_state_review
from .static_transfer_review import run_static_transfer_review


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


def _infer_go_variable_type(text: str, variable: str, before_offset: int) -> str | None:
    before = text[:before_offset]
    candidates: list[tuple[int, str]] = []

    for match in re.finditer(
        rf"\b{re.escape(variable)}\s*(?::=|=)\s*&(?P<type>[A-Za-z_][A-Za-z0-9_.]*)\s*\{{",
        before,
    ):
        candidates.append((match.start(), match.group("type")))

    for match in re.finditer(
        rf"func\s*(?:\([^)]*\)\s*)?[A-Za-z_][A-Za-z0-9_]*\s*\((?P<params>[^)]*)\)",
        before,
        re.S,
    ):
        params = match.group("params")
        parameter = re.search(
            rf"(?:^|,)\s*{re.escape(variable)}\s+\*(?P<type>[A-Za-z_][A-Za-z0-9_.]*)\b",
            params,
            re.S,
        )
        if parameter is not None:
            candidates.append((match.start(), parameter.group("type")))

    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def run_static_status_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    writers: dict[str, list[tuple[str, int, str]]] = defaultdict(list)

    for path in changed:
        if Path(path).suffix.lower() != ".go":
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        for update in re.finditer(
            r"\.Status\(\)\.Update\s*\(\s*[^,]+,\s*(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*\)",
            text,
        ):
            variable = update.group("var")
            resource_type = _infer_go_variable_type(text, variable, update.start())
            if resource_type is None:
                continue
            writers[resource_type].append((path, _line(text, update.start()), variable))

    findings: list[dict[str, Any]] = []
    for resource_type, rows in writers.items():
        distinct_paths = sorted({path for path, _, _ in rows})
        if len(distinct_paths) < 2:
            continue
        first_path, first_line, _ = rows[0]
        refs = sorted({f"{path}:{line}" for path, line, _ in rows})
        findings.append(
            {
                "source": "static-status-officer",
                "officer": "Mechanic",
                "capability": "concurrency",
                "category": "concurrency",
                "severity": "major",
                "root_cause": "shared-status-full-replacement",
                "path": first_path,
                "line_start": first_line,
                "line_end": first_line,
                "evidence_ref": f"{first_path}:{first_line}",
                "supporting_evidence_refs": refs,
                "message": "Independent controllers fully replace the same status object and can overwrite fields owned by one another.",
                "evidence": (
                    f"{len(distinct_paths)} controller files call Status().Update on {resource_type}. "
                    "The object type is recovered from both local allocations and typed function parameters; "
                    "full status replacement can therefore race across separate reconcilers."
                ),
                "falsifiers_checked": [
                    "Checked that the same resource type is written from more than one controller file.",
                    "Checked local allocations and typed function parameters for the updated object.",
                    "Checked that the relevant writes use Status().Update rather than field-scoped MergeFrom patches.",
                ],
                "verification_test": (
                    "Fetch the latest object, patch only fields owned by each controller with MergeFrom, "
                    "and retry conflicts so unrelated status fields survive concurrent reconciliation."
                ),
                "confidence": 0.96,
                "direct_evidence": True,
                "admission_hint": "actionable",
            }
        )

    recovery = run_static_recovery_review(root_path, changed)
    findings.extend(
        dict(item)
        for item in recovery.get("findings", [])
        if isinstance(item, dict)
    )
    stale_state = run_static_stale_state_review(root_path, changed)
    findings.extend(
        dict(item)
        for item in stale_state.get("findings", [])
        if isinstance(item, dict)
    )
    transfer = run_static_transfer_review(root_path, changed)
    findings.extend(
        dict(item)
        for item in transfer.get("findings", [])
        if isinstance(item, dict)
    )
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding.get("root_cause")), str(finding.get("path")))] = finding

    return {
        "schema_version": "sergeant.static-status-review.v4",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "resource_writers": {
            resource_type: [
                {"path": path, "line": line, "variable": variable}
                for path, line, variable in rows
            ]
            for resource_type, rows in writers.items()
        },
        "static_recovery_review": recovery,
        "static_stale_state_review": stale_state,
        "static_transfer_review": transfer,
        "executed_project_code": False,
    }
