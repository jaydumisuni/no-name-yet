"""Static invariants that require code understanding but not project execution."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Iterable

from .static_cross_path_review import run_static_cross_path_review
from .static_job_recovery_review import run_static_job_recovery_review
from .static_roundtrip_review import run_static_roundtrip_review
from .static_status_review import run_static_status_review

_SOURCE_SUFFIXES = {".py", ".go", ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}


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


def _finding(
    *, officer: str, capability: str, severity: str, root_cause: str, path: str,
    line_start: int, message: str, evidence: str, falsifiers: Iterable[str],
    verification: str, confidence: float,
) -> dict[str, Any]:
    return {
        "source": "static-invariant-officer",
        "officer": officer,
        "capability": capability,
        "category": capability,
        "severity": severity,
        "root_cause": root_cause,
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": f"{path}:{line_start}",
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": list(falsifiers),
        "verification_test": verification,
        "confidence": confidence,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def _python_source_segment(text: str, node: ast.AST) -> tuple[str, int]:
    lines = text.splitlines(keepends=True)
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start)
    return "".join(lines[start - 1:end]), start


def _python_delivery_without_ack(path: str, text: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    findings: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = node.name.lower()
        if "start" not in name or "session" not in name:
            continue
        body, line_start = _python_source_segment(text, node)
        delivery_assign = re.search(r"\b(?P<flag>(?:sent|delivered|dispatched|published)_to_[A-Za-z0-9_]+|(?:sent|delivered|dispatched))\s*=\s*False\b", body)
        if delivery_assign is None:
            continue
        flag = delivery_assign.group("flag")
        if not re.search(r"\b(?:send_text|send_json|send|publish|dispatch)\s*\(", body):
            continue
        running_return = re.search(r"[\"']status[\"']\s*:\s*[\"'](?:running|active|started)[\"']", body, re.I)
        if running_return is None:
            continue
        failure_guard = re.search(
            rf"if\s+not\s+{re.escape(flag)}\s*:[\s\S]{{0,1200}}(?:return\s+\{{[\s\S]{{0,300}}[\"'](?:error|failed)[\"']|raise\s+)",
            body,
            re.I,
        )
        if failure_guard is not None:
            continue
        findings.append(
            _finding(
                officer="Mechanic",
                capability="state_lifecycle",
                severity="major",
                root_cause="active-state-without-delivery-ack",
                path=path,
                line_start=line_start + body[: running_return.start()].count("\n"),
                message="A session can be reported active even when its required task delivery was never acknowledged.",
                evidence=f"{node.name} initializes delivery flag {flag}=False and returns running/active state without a fail-closed branch proving that flag became true.",
                falsifiers=(
                    "Checked for an explicit failure return or exception when delivery remains false.",
                    "Checked that a real outbound send/publish/dispatch operation exists.",
                    "Checked whether active state is returned only inside a confirmed-success branch.",
                ),
                verification="Do not publish running/active state until delivery succeeds; on failure release all allocated session state and return a failed result.",
                confidence=0.96,
            )
        )
    return findings


def _go_unstable_persisted_order(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    map_names = {
        match.group("name")
        for match in re.finditer(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?::=|=)\s*(?:make\s*\(\s*)?map\[", text)
    }
    for map_name in map_names:
        loop = re.search(
            rf"for\s+(?:[A-Za-z_][A-Za-z0-9_]*\s*,\s*)?(?P<item>[A-Za-z_][A-Za-z0-9_]*)\s*:=\s*range\s+{re.escape(map_name)}\s*\{{(?P<body>[\s\S]{{0,700}}?)\}}",
            text,
        )
        if loop is None:
            continue
        append = re.search(
            rf"(?P<target>[A-Za-z_][A-Za-z0-9_.]*)\s*=\s*append\s*\(\s*(?P=target)\s*,\s*{re.escape(loop.group('item'))}\s*\)",
            loop.group("body"),
        )
        if append is None:
            continue
        target = append.group("target")
        sorted_target = re.search(
            rf"(?:sort\.(?:Strings|Slice|SliceStable)|slices\.Sort(?:Func)?)\s*\(\s*{re.escape(target)}\b",
            text[loop.end() : loop.end() + 1200],
        )
        if sorted_target is not None:
            continue
        if not re.search(r"(?:spec|config|resource|secret|volume|mount|rule|policy|merged)", target, re.I):
            continue
        findings.append(
            _finding(
                officer="Mechanic",
                capability="state_lifecycle",
                severity="major",
                root_cause="nondeterministic-persisted-order",
                path=path,
                line_start=_line(text, loop.start()),
                message="Map iteration is published as ordered configuration without canonical sorting.",
                evidence=f"Values from Go map {map_name} are appended directly into {target}; Go map order is nondeterministic and no sort of that target follows before publication.",
                falsifiers=(
                    "Checked for sort.Strings, sort.Slice, sort.SliceStable, or slices.Sort on the emitted target.",
                    "Checked that the target represents configuration/spec/resource state where order affects equality or reconciliation.",
                    "Checked that the source is a Go map rather than an ordered collection.",
                ),
                verification="Sort the emitted slice canonically before assigning or persisting it, then prove repeated reconciliation produces byte-for-byte stable state.",
                confidence=0.96,
            )
        )
    return findings


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
            if char == "\n": line_comment = False
            index += 1; continue
        if block_comment:
            if char == "*" and nxt == "/": block_comment = False; index += 2
            else: index += 1
            continue
        if quote is not None:
            if escaped: escaped = False
            elif char == "\\": escaped = True
            elif char == quote: quote = None
            index += 1; continue
        if char == "/" and nxt == "/": line_comment = True; index += 2; continue
        if char == "/" and nxt == "*": block_comment = True; index += 2; continue
        if char in {"'", '"'}: quote = char; index += 1; continue
        if char == "{": depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0: return index
        index += 1
    return None


def _cpp_end_bound_dereference(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    signature_re = re.compile(
        r"(?P<signature>[A-Za-z0-9_:<>,*&\s]+\((?P<params>[^)]*\b(?:const\s+)?char\s*\*\s*(?P<ptr>[A-Za-z_][A-Za-z0-9_]*)[^)]*\b(?:const\s+)?char\s*\*\s*(?P<end>end|last|finish)[^)]*)\)\s*(?:const\s*)?(?:noexcept\s*)?\{)",
        re.M,
    )
    for match in signature_re.finditer(text):
        opening = match.end() - 1
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        ptr = match.group("ptr")
        end = match.group("end")
        body = text[opening + 1:closing]
        deref = re.search(rf"\*\s*{re.escape(ptr)}\b|{re.escape(ptr)}\s*\[\s*0\s*\]", body)
        if deref is None:
            continue
        before = body[:deref.start()]
        guarded = bool(
            re.search(rf"{re.escape(ptr)}\s*(?:>=|==)\s*{re.escape(end)}", before)
            or re.search(rf"{re.escape(ptr)}\s*<\s*{re.escape(end)}[^\n]*\*\s*{re.escape(ptr)}", before)
        )
        if guarded:
            continue
        name_match = re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", match.group("signature"))
        function_name = name_match[-1] if name_match else "scanner"
        if not re.search(r"(?:parse|scan|skip|read|lex|json|token|key|value)", function_name, re.I):
            continue
        findings.append(
            _finding(
                officer="Medic",
                capability="memory_safety",
                severity="blocker",
                root_cause="cursor-dereference-before-end-check",
                path=path,
                line_start=_line(text, opening + 1 + deref.start()),
                message="A bounded parser dereferences its cursor before proving it is before the supplied end pointer.",
                evidence=f"Function {function_name} accepts cursor {ptr} and bound {end}, but the first dereference of {ptr} is not dominated by a {ptr} < {end} or {ptr} >= {end} guard.",
                falsifiers=(
                    "Checked for an end guard before the first dereference.",
                    "Checked whether the function is a parser/scanner/reader where truncated input can reach the boundary.",
                    "Checked whether the dereference is guarded in the same short-circuit expression.",
                ),
                verification="Guard the cursor against the authoritative end before every dereference and clamp fixed-width skips so truncated input cannot move or read beyond the buffer.",
                confidence=0.97,
            )
        )
    return findings


def run_static_invariant_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    findings: list[dict[str, Any]] = []
    readable: list[str] = []
    for path in changed:
        suffix = Path(path).suffix.lower()
        if suffix not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        if suffix == ".py": findings.extend(_python_delivery_without_ack(path, text))
        elif suffix == ".go": findings.extend(_go_unstable_persisted_order(path, text))
        elif suffix in {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}:
            findings.extend(_cpp_end_bound_dereference(path, text))
    cross_path = run_static_cross_path_review(root_path, changed)
    findings.extend(dict(item) for item in cross_path.get("findings", []) if isinstance(item, dict))
    status_review = run_static_status_review(root_path, changed)
    findings.extend(dict(item) for item in status_review.get("findings", []) if isinstance(item, dict))
    roundtrip_review = run_static_roundtrip_review(root_path, changed)
    findings.extend(dict(item) for item in roundtrip_review.get("findings", []) if isinstance(item, dict))
    job_recovery_review = run_static_job_recovery_review(root_path, changed)
    findings.extend(dict(item) for item in job_recovery_review.get("findings", []) if isinstance(item, dict))
    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding["root_cause"]), str(finding["path"]), int(finding["line_start"]))] = finding
    return {
        "schema_version": "sergeant.static-invariant-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "static_cross_path_review": cross_path,
        "static_status_review": status_review,
        "static_roundtrip_review": roundtrip_review,
        "static_job_recovery_review": job_recovery_review,
        "executed_project_code": False,
    }
