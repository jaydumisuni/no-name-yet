"""Static review of durable job recovery and retry-budget invariants."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Iterable


def _safe_text(root: Path, relative: str) -> str:
    try:
        resolved_root = root.resolve()
        path = (resolved_root / relative).resolve()
        if not path.is_relative_to(resolved_root) or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _function_segments(text: str) -> list[tuple[str, str, int]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    lines = text.splitlines(keepends=True)
    segments: list[tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end = getattr(node, "end_lineno", node.lineno)
        segments.append((node.name, "".join(lines[node.lineno - 1 : end]), node.lineno))
    return segments


def run_static_job_recovery_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    findings: list[dict[str, Any]] = []

    for path in changed:
        if Path(path).suffix.lower() != ".py":
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        for function_name, body, line_start in _function_segments(text):
            if not re.search(r"(?:acquire|claim|reclaim|lease|dequeue|reserve).*(?:job|task)|(?:job|task).*(?:acquire|claim|reclaim|lease)", function_name, re.I):
                continue
            stale_selection = bool(
                re.search(r"state\s*=\s*['\"]pending['\"]", body, re.I)
                and re.search(r"state\s*=\s*['\"]started['\"]", body, re.I)
                and re.search(r"heartbeat|stale|started_at|lease|locked_at", body, re.I)
            )
            if not stale_selection:
                continue
            ownership_reset = bool(
                re.search(r"SET[\s\S]{0,800}(?:worker_id|owner_id|lease_owner|heartbeat|started_at)", body, re.I)
                or re.search(r"(?:worker_id|owner_id|lease_owner|heartbeat|started_at)\s*=", body, re.I)
            )
            if not ownership_reset:
                continue
            advances_attempts = bool(
                re.search(r"attempts?\s*=\s*(?:attempts?\s*\+\s*1|COALESCE\s*\(\s*attempts?[^)]*\)\s*\+\s*1)", body, re.I)
                or re.search(r"(?:attempts?|retry_count)\s*\+=\s*1", body, re.I)
            )
            exhaustion = bool(
                re.search(r"max_retr(?:y|ies)|retry_limit|max_attempts", body, re.I)
                and re.search(r"failed|exhaust|dead|terminal", body, re.I)
            )
            distinguishes_reclaim = bool(
                re.search(r"(?:selected_)?state|previous_state|was_started|is_reclaim", body, re.I)
            )
            if advances_attempts and exhaustion and distinguishes_reclaim:
                continue

            marker = re.search(r"state\s*=\s*['\"]started['\"]", body, re.I)
            finding_line = line_start + body[: marker.start() if marker else 0].count("\n")
            findings.append(
                {
                    "source": "static-job-recovery-officer",
                    "officer": "Mechanic",
                    "capability": "state_lifecycle",
                    "category": "state_lifecycle",
                    "severity": "major",
                    "root_cause": "stale-reclaim-budget-not-advanced",
                    "path": path,
                    "line_start": finding_line,
                    "line_end": finding_line,
                    "evidence_ref": f"{path}:{finding_line}",
                    "message": "A stale running job can be reclaimed repeatedly without consuming its retry budget or reaching a terminal state.",
                    "evidence": (
                        f"{function_name} selects pending jobs and stale started jobs through the same acquisition path, "
                        "then resets ownership/heartbeat state without proving that a reclaim increments attempts and "
                        "enforces the finite retry limit. Process death can therefore bypass every ordinary failure counter."
                    ),
                    "falsifiers_checked": [
                        "Checked for a reclaim-specific previous-state branch.",
                        "Checked for attempts/retry_count increment on stale reclaim.",
                        "Checked for max-retry exhaustion that persists a failed terminal state.",
                    ],
                    "verification_test": (
                        "Select the previous state and retry counters under the same row lock; on stale reclaim increment "
                        "attempts, persist terminal failure when a finite limit is exhausted, and commit that state before returning."
                    ),
                    "confidence": 0.97,
                    "direct_evidence": True,
                    "admission_hint": "actionable",
                }
            )

    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding["root_cause"]), str(finding["path"]))] = finding
    return {
        "schema_version": "sergeant.static-job-recovery-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "executed_project_code": False,
    }
