"""Static persistence checks for monotonic terminal state."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_TERMINAL = {"completed", "failed", "cancelled", "canceled", "interrupted", "aborted", "terminated"}
_PROGRESS_MARKERS = (
    "processed", "failed_files", "progress", "heartbeat", "updated_at", "completed_count", "current_step"
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


def _matching_brace(text: str, opening: int) -> int | None:
    depth = 0
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    index = opening
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char == "/" and nxt == "/":
            line_comment = True
            index += 2
            continue
        if char == "/" and nxt == "*":
            block_comment = True
            index += 2
            continue
        if char in {"'", '"', "`"}:
            quote = char
            index += 1
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _terminal_literals(text: str) -> set[str]:
    lowered = text.lower()
    return {state for state in _TERMINAL if re.search(rf"[\"']{re.escape(state)}[\"']", lowered)}


def _guarded(sql: str) -> bool:
    return bool(
        re.search(r"\bstatus\s+NOT\s+IN\s*\(", sql, re.I)
        or re.search(r"\bstatus\s+IN\s*\(", sql, re.I)
        or re.search(r"\bCASE\s+WHEN\s+status\b", sql, re.I)
        or re.search(r"\bWHERE[\s\S]*\bstatus\s*(?:=|!=|<>)", sql, re.I)
    )


def _finding(path: str, line: int, function_name: str, terminal: set[str]) -> dict[str, Any]:
    states = ", ".join(sorted(terminal))
    return {
        "source": "static-terminal-state-officer",
        "officer": "Mechanic",
        "capability": "state_lifecycle",
        "category": "state_lifecycle",
        "severity": "major",
        "root_cause": "nonterminal-progress-can-overwrite-terminal-state",
        "path": path,
        "line_start": line,
        "line_end": line,
        "evidence_ref": f"{path}:{line}",
        "supporting_evidence_refs": [f"{path}:{line}"],
        "message": "A stale progress write can overwrite an already terminal persisted state.",
        "evidence": (
            f"{function_name} updates status together with progress fields using an unconditional row UPDATE. "
            f"The surrounding contract contains terminal states ({states}), but the persistence predicate does not exclude them."
        ),
        "falsifiers_checked": [
            "Checked that the write updates status together with progress/heartbeat fields rather than being a deliberate status transition.",
            "Checked that multiple terminal state literals exist in the local persistence contract.",
            "Checked the SQL predicate for status NOT IN/IN, status comparison, or CASE-based monotonic protection.",
        ],
        "verification_test": (
            "Make non-terminal progress writes conditional on the current row not being terminal, and prove a late running/progress "
            "snapshot cannot resurrect completed, failed, cancelled or interrupted records."
        ),
        "confidence": 0.97,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def run_static_terminal_state_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    findings: list[dict[str, Any]] = []
    readable: list[str] = []

    function_re = re.compile(r"func\s*(?:\([^)]*\)\s*)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)[^{]*\{", re.M)
    sql_re = re.compile(r"UPDATE\s+[A-Za-z0-9_]+[\s\S]{0,1800}?WHERE\s+[A-Za-z0-9_.]+\s*=\s*\?", re.I)

    for path in changed:
        if Path(path).suffix.lower() != ".go":
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        terminal = _terminal_literals(text)
        if len(terminal) < 2:
            continue
        for function in function_re.finditer(text):
            opening = function.end() - 1
            closing = _matching_brace(text, opening)
            if closing is None:
                continue
            body = text[opening + 1 : closing]
            if "status" not in body.lower():
                continue
            if not any(marker in body.lower() for marker in _PROGRESS_MARKERS):
                continue
            for sql in sql_re.finditer(body):
                statement = sql.group(0)
                if re.search(r"SET[\s\S]{0,500}\bstatus\s*=", statement, re.I) is None:
                    continue
                if _guarded(statement):
                    continue
                line = _line(text, opening + 1 + sql.start())
                findings.append(_finding(path, line, function.group("name"), terminal))
                break

    unique = {(str(item["root_cause"]), str(item["path"])): item for item in findings}
    return {
        "schema_version": "sergeant.static-terminal-state-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
