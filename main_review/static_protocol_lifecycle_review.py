"""Static protocol-resource lifecycle review for C-family code."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Iterator

_SOURCE_SUFFIXES = {".c", ".h"}
_ID_FIELDS = r"(?:id|stream_id|handle|fd|channel_id)"
_ACTION_CALL_RE = re.compile(
    r"\b[A-Za-z0-9_]*(?:submit|send|queue|write|dispatch|flush|frame|priority)"
    r"[A-Za-z0-9_]*\s*\(",
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


def _matching(text: str, opening: int, left: str, right: str) -> int | None:
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
        if char in {'"', "'"}:
            quote = char
            index += 1
            continue
        if char == left:
            depth += 1
        elif char == right:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _braced_ifs(text: str) -> Iterator[tuple[int, str, str]]:
    for match in re.finditer(r"\bif\s*\(", text):
        opening = text.find("(", match.start(), match.end())
        if opening < 0:
            continue
        closing = _matching(text, opening, "(", ")")
        if closing is None:
            continue
        cursor = closing + 1
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor >= len(text) or text[cursor] != "{":
            continue
        end = _matching(text, cursor, "{", "}")
        if end is None:
            continue
        yield match.start(), text[opening + 1 : closing], text[cursor + 1 : end]


def _finding(path: str, line_start: int, variable: str, factory: str, identity: str) -> dict[str, Any]:
    primary = f"{path}:{line_start}"
    return {
        "source": "static-protocol-lifecycle-officer",
        "officer": "Mechanic",
        "capability": "protocol_lifecycle",
        "category": "correctness",
        "severity": "blocker",
        "root_cause": "protocol-operation-uses-resource-before-open-identity",
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": primary,
        "supporting_evidence_refs": [primary],
        "message": (
            "A protocol operation dereferences a stream/session resource before proving that the resource exists and has an opened protocol identity."
        ),
        "evidence": (
            f"`{variable}` is obtained from `{factory}(...)`. A later protocol-action branch dereferences `{identity}` without proving both pointer existence and a usable protocol identity. "
            "The branch can execute before the stream/session has opened."
        ),
        "falsifiers_checked": [
            "Required a pointer-valued stream/session/channel/context resource obtained inside the function.",
            "Required a braced action branch that dereferences a protocol identity.",
            "Recognized prefixed action calls such as vendor_submit_priority and library_send_frame.",
            "Checked for an earlier fail-fast null guard.",
            "Checked for both pointer existence and positive/non-sentinel identity guards in the action condition.",
            "Excluded guarded operations and non-protocol pointer use.",
        ],
        "verification_test": (
            "Gate the action on resource existence and an opened positive/non-sentinel protocol identity; test changes before open, during open, and after close."
        ),
        "confidence": 0.99,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def _findings(path: str, text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    assignments = re.compile(
        r"\bstruct\s+[A-Za-z_][A-Za-z0-9_]*\s*\*\s*(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
        r"(?P<factory>[A-Za-z_][A-Za-z0-9_]*)\s*\([^;\n]*\)\s*;",
        re.M,
    )
    for assignment in assignments.finditer(text):
        variable = assignment.group("var")
        if not re.search(r"(?:stream|session|channel|connection|context|ctx)", variable, re.I):
            continue
        window = text[assignment.end() : assignment.end() + 3500]
        for branch_start, condition, body in _braced_ifs(window):
            identity = re.search(rf"\b{re.escape(variable)}\s*->\s*{_ID_FIELDS}\b", body)
            if identity is None or _ACTION_CALL_RE.search(body) is None:
                continue
            prefix = window[:branch_start]
            fail_fast = re.search(
                rf"\bif\s*\(\s*(?:!\s*{re.escape(variable)}|{re.escape(variable)}\s*==\s*(?:NULL|0))\s*\)"
                rf"[\s\S]{{0,180}}?(?:return|goto|continue|break)\b",
                prefix[-800:],
                re.M,
            )
            pointer_guard = re.search(
                rf"(?:\b{re.escape(variable)}\s*&&|\b{re.escape(variable)}\s*!=\s*(?:NULL|0))",
                condition,
            )
            identity_guard = re.search(
                rf"\b{re.escape(variable)}\s*->\s*{_ID_FIELDS}\s*(?:>|>=|!=)\s*(?:0|-1)",
                condition,
            )
            if fail_fast or (pointer_guard and identity_guard):
                continue
            results.append(
                _finding(
                    path,
                    _line(text, assignment.end() + branch_start),
                    variable,
                    assignment.group("factory"),
                    identity.group(0),
                )
            )
            break
    return results


def run_static_protocol_lifecycle_review(
    root: str | Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    readable: list[str] = []
    findings: list[dict[str, Any]] = []
    for path in changed:
        if Path(path).suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        findings.extend(_findings(path, text))

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[(
            str(finding.get("root_cause")),
            str(finding.get("path")),
            int(finding.get("line_start") or 0),
        )] = finding
    return {
        "schema_version": "sergeant.static-protocol-lifecycle-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
