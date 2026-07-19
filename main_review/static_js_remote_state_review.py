"""Static JavaScript/TypeScript remote-to-local state ordering review."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}
_ASYNC_FUNCTION_RE = re.compile(
    r"(?:async\s+function\s+(?P<decl>[A-Za-z_$][\w$]*)\s*\([^)]*\)|"
    r"(?:const|let|var)\s+(?P<arrow>[A-Za-z_$][\w$]*)\s*=\s*async\s*\([^)]*\)\s*=>)\s*\{",
    re.M,
)
_PLAIN_FUNCTION_RE = re.compile(r"function\s+(?P<name>[A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{", re.M)
_MODULE_EMPTY_RE = re.compile(
    r"^(?:export\s+)?(?:let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:null|undefined|false)\s*;?",
    re.M,
)
_AWAIT_STATEMENT_RE = re.compile(r"\bawait\s+(?P<statement>[\s\S]{1,900}?);", re.M)


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


def _functions(text: str, pattern: re.Pattern[str]) -> dict[str, tuple[str, int]]:
    functions: dict[str, tuple[str, int]] = {}
    for match in pattern.finditer(text):
        groups = match.groupdict()
        name = groups.get("decl") or groups.get("arrow") or groups.get("name")
        if not name:
            continue
        opening = match.end() - 1
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        functions[name] = (text[opening + 1 : closing], opening + 1)
    return functions


def _finding(
    *,
    path: str,
    line_start: int,
    function_name: str,
    shared: str,
    await_line: int,
    helper_name: str,
    helper_line: int,
    declaration_line: int,
) -> dict[str, Any]:
    return {
        "source": "static-js-remote-state-officer",
        "officer": "Mechanic",
        "capability": "state_lifecycle",
        "category": "state_lifecycle",
        "severity": "major",
        "root_cause": "local-state-not-established-before-await",
        "path": path,
        "line_start": await_line,
        "line_end": await_line,
        "evidence_ref": f"{path}:{await_line}",
        "supporting_evidence_refs": [
            f"{path}:{declaration_line}",
            f"{path}:{await_line}",
            f"{path}:{helper_line}",
        ],
        "message": "An async action awaits remote persistence before establishing local state required by its immediate continuation.",
        "evidence": (
            f"{function_name} writes the remote {shared} resource and suspends at line {await_line} while local {shared} "
            f"still has its empty initial value; {helper_name} then dereferences that local state at line {helper_line}."
        ),
        "falsifiers_checked": [
            "Checked for assignment of the consumed local/shared state before the await.",
            "Checked that the awaited remote statement names the same resource identity as the local state.",
            "Checked that the immediate continuation calls a helper that dereferences the local state.",
            "Checked that the local state is module-scoped and starts empty rather than being call-local.",
        ],
        "verification_test": (
            "Establish local ownership/state before the remote await, roll it back on persistence failure if needed, "
            "and prove the immediate continuation always receives the new identity."
        ),
        "confidence": 0.97,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def _remote_local_ordering(path: str, text: str) -> list[dict[str, Any]]:
    async_functions = _functions(text, _ASYNC_FUNCTION_RE)
    helpers = _functions(text, _PLAIN_FUNCTION_RE)
    declarations = {
        match.group("name"): (match.start(), _line(text, match.start()))
        for match in _MODULE_EMPTY_RE.finditer(text)
    }
    findings: list[dict[str, Any]] = []

    for function_name, (body, body_offset) in async_functions.items():
        for awaited in _AWAIT_STATEMENT_RE.finditer(body):
            before = body[: awaited.start()]
            after = body[awaited.end() :]
            remote_statement = awaited.group("statement")
            await_line = _line(text, body_offset + awaited.start())
            for helper_name, (helper_body, _) in helpers.items():
                helper_call = re.search(rf"\b{re.escape(helper_name)}\s*\(", after)
                if helper_call is None:
                    continue
                helper_line = _line(text, body_offset + awaited.end() + helper_call.start())
                for shared, (_, declaration_line) in declarations.items():
                    if not re.search(rf"\b{re.escape(shared)}\s*(?:\?\.|\.|\[)", helper_body):
                        continue
                    if re.search(rf"\b{re.escape(shared)}\s*=", before):
                        continue
                    if shared.lower() not in remote_statement.lower():
                        continue
                    findings.append(
                        _finding(
                            path=path,
                            line_start=await_line,
                            function_name=function_name,
                            shared=shared,
                            await_line=await_line,
                            helper_name=helper_name,
                            helper_line=helper_line,
                            declaration_line=declaration_line,
                        )
                    )
    return findings


def run_static_js_remote_state_review(
    root: str | Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    findings: list[dict[str, Any]] = []
    readable: list[str] = []
    for path in changed:
        if Path(path).suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        findings.extend(_remote_local_ordering(path, text))

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[
            (
                str(finding.get("root_cause")),
                str(finding.get("path")),
                int(finding.get("line_start", 0)),
            )
        ] = finding
    return {
        "schema_version": "sergeant.static-js-remote-state-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
