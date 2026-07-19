"""Static checks for filesystem containment, interpreter boundaries, and HTTP response ownership."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_SOURCE_SUFFIXES = {".cs", ".rs", ".go"}
_PATH_CONTEXT_RE = re.compile(r"(?:guest|mount|app0|sandbox|workspace|upload|extract|archive)", re.I)
_ROOT_NAME_RE = re.compile(r"(?:root|mount|base|sandbox|workspace|upload|extract|app0)", re.I)
_TAINT_NAME_RE = re.compile(r"(?:guest|relative|request|input|user|path)", re.I)


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


def _finding(
    *,
    root_cause: str,
    path: str,
    line_start: int,
    severity: str,
    category: str,
    officer: str,
    message: str,
    evidence: str,
    falsifiers: Iterable[str],
    verification: str,
    confidence: float = 0.97,
) -> dict[str, Any]:
    return {
        "source": "static-transfer-9-officer",
        "officer": officer,
        "capability": category,
        "category": category,
        "severity": severity,
        "root_cause": root_cause,
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": f"{path}:{line_start}",
        "supporting_evidence_refs": [f"{path}:{line_start}"],
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": list(falsifiers),
        "verification_test": verification,
        "confidence": confidence,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def _normalizer_body(text: str, name: str) -> str:
    method = re.search(
        rf"(?:private|public|internal|protected)?\s*static\s+string\??\s+{re.escape(name)}\s*\([^)]*\)\s*\{{",
        text,
        re.I | re.M,
    )
    if method is None:
        return ""
    opening = method.end() - 1
    closing = _matching_brace(text, opening)
    return text[opening + 1 : closing] if closing is not None else ""


def _normalizer_proves_containment(text: str, name: str) -> bool:
    body = _normalizer_body(text, name)
    if not body:
        return False
    resolves_dotdot = bool(
        re.search(r"(?:segment|part)\s*==\s*[\"']\.\.[\"']", body, re.I)
        and re.search(r"(?:RemoveAt|Pop\s*\(|\.pop\s*\(|resolved\.Count\s*>\s*0)", body, re.I)
    )
    canonical_and_guarded = bool(
        re.search(r"Path\.GetFullPath\s*\(", body)
        and re.search(r"(?:StartsWith|string\.Equals|Path\.GetRelativePath)", body)
        and re.search(r"(?:root|mount|base)", body, re.I)
    )
    return resolves_dotdot or canonical_and_guarded


def _path_containment_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() != ".cs" or _PATH_CONTEXT_RE.search(f"{path}\n{text}") is None:
        return []
    findings: list[dict[str, Any]] = []
    combine_re = re.compile(
        r"Path\.Combine\s*\(\s*(?P<root>[A-Za-z_][A-Za-z0-9_.]*)\s*,\s*(?P<relative>[A-Za-z_][A-Za-z0-9_.]*(?:\s*\([^)]*\))?)\s*\)",
        re.M,
    )
    for combine in combine_re.finditer(text):
        root_expr = combine.group("root")
        relative_expr = combine.group("relative").strip()
        if _ROOT_NAME_RE.search(root_expr) is None:
            continue
        before = text[max(0, combine.start() - 1400) : combine.start()]
        around = text[max(0, combine.start() - 120) : min(len(text), combine.end() + 700)]
        if re.search(r"Path\.GetFullPath\s*\([^;\n]*$", before[-160:], re.I):
            if re.search(r"(?:StartsWith|string\.Equals|Path\.GetRelativePath)", around, re.I):
                continue

        normalizer_call = re.match(r"(?P<name>Normalize[A-Za-z0-9_]*)\s*\(", relative_expr)
        unsafe = False
        if normalizer_call is not None:
            unsafe = not _normalizer_proves_containment(text, normalizer_call.group("name"))
        else:
            variable = relative_expr.split(".")[-1]
            assignments = list(
                re.finditer(
                    rf"\b(?:var|string)\s+{re.escape(variable)}\s*=\s*(?P<source>[^;]+);",
                    before,
                    re.I,
                )
            )
            if assignments:
                source = assignments[-1].group("source")
                assigned_normalizer = re.match(r"(?P<name>Normalize[A-Za-z0-9_]*)\s*\(", source.strip())
                if assigned_normalizer is not None:
                    unsafe = not _normalizer_proves_containment(text, assigned_normalizer.group("name"))
                else:
                    unsafe = bool(_TAINT_NAME_RE.search(source))
            elif _TAINT_NAME_RE.search(relative_expr):
                unsafe = True
        if not unsafe:
            continue
        line = _line(text, combine.start())
        findings.append(
            _finding(
                root_cause="untrusted-relative-path-can-escape-mounted-root",
                path=path,
                line_start=line,
                severity="blocker",
                category="security_taint",
                officer="Medic",
                message="An untrusted relative path is combined with a trusted mount root without proving traversal normalization and containment.",
                evidence=(
                    "The filesystem sink combines a mount/root path with guest- or request-derived relative input. The local path transformation "
                    "does not establish that `..` segments are resolved and clamped, and the resulting candidate is not canonically checked against the root."
                ),
                falsifiers=(
                    "Checked whether the relative input is fixed or derived from guest/request/path data.",
                    "Checked for explicit dot-segment stack resolution or rejection.",
                    "Checked for Path.GetFullPath plus a root-prefix/relative-path containment proof at the same sink.",
                    "Checked whether the named normalizer itself proves containment rather than only changing separators.",
                ),
                verification=(
                    "Resolve dot segments under the intended mount policy, canonicalize the candidate, enforce that it remains at or below the trusted root, "
                    "and prove `..`, mixed separators and rooted inputs cannot reach a sibling or parent host directory."
                ),
            )
        )
        break
    return findings


def _interpreter_boundary_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() != ".rs":
        return []
    findings: list[dict[str, Any]] = []
    source_flag = re.compile(r"[\"']-c[\"']", re.M)
    for flag in source_flag.finditer(text):
        window_start = max(0, flag.start() - 500)
        window_end = min(len(text), flag.end() + 2600)
        window = text[window_start:window_end]
        if re.search(r"(?:python|python_run|python_bin)", window, re.I) is None:
            continue
        formatter = re.search(r"format!\s*\(", window[flag.start() - window_start :], re.M)
        if formatter is None:
            continue
        formatted = window[flag.start() - window_start + formatter.start() :]
        if re.search(r"(?:params\.)?(?:query|path|input|request|user)[A-Za-z0-9_.]*", formatted, re.I) is None:
            continue
        if re.search(r"ORGANON_BRIDGE_ARGS|serde_json::json!|\.env\s*\(", window, re.I):
            continue
        line = _line(text, flag.start())
        findings.append(
            _finding(
                root_cause="untrusted-data-interpolated-into-interpreter-source",
                path=path,
                line_start=line,
                severity="blocker",
                category="security_taint",
                officer="Engineer",
                message="User-controlled values are formatted into source code passed to an interpreter.",
                evidence=(
                    "The process invocation uses an interpreter source flag (`-c`) and constructs that source with `format!` containing query/path/input values. "
                    "Language-specific debug escaping is not an argument boundary and can break or reshape executable source."
                ),
                falsifiers=(
                    "Checked that the interpreter receives source through `-c` rather than a fixed module/script entry point.",
                    "Checked that the source is dynamically formatted with request/query/path-like values.",
                    "Checked for structured argv, JSON stdin/environment, or another data-only transport.",
                    "Checked that a fixed source string with separately passed arguments is not being flagged.",
                ),
                verification=(
                    "Invoke a fixed module or script and pass untrusted values through structured argv, JSON stdin or a dedicated environment payload; "
                    "prove quotes, control characters and source-language delimiters remain data."
                ),
            )
        )
        break
    return findings


def _go_function_blocks(text: str) -> Iterable[tuple[str, str, int]]:
    function_re = re.compile(
        r"\bfunc\s*(?:\([^)]*\)\s*)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)[^{]*\{",
        re.M,
    )
    for function in function_re.finditer(text):
        opening = function.end() - 1
        closing = _matching_brace(text, opening)
        if closing is not None:
            yield function.group("name"), text[opening + 1 : closing], opening + 1


def _http_response_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() != ".go":
        return []
    findings: list[dict[str, Any]] = []
    for function_name, body, body_offset in _go_function_blocks(text):
        for read in re.finditer(
            r"(?:io\.ReadAll\s*\(|json\.NewDecoder\s*\(|io\.Copy\s*\([^,]+,\s*)(?P<response>[A-Za-z_][A-Za-z0-9_]*)\.Body",
            body,
            re.M,
        ):
            response = read.group("response")
            before = body[: read.start()]
            ownership = list(
                re.finditer(
                    rf"\b{re.escape(response)}\s*,\s*(?:err|_)\s*:=\s*(?P<call>[^\n;]+)",
                    before,
                    re.M,
                )
            )
            if not ownership:
                continue
            close_re = re.compile(rf"(?:defer\s+)?{re.escape(response)}\.Body\.Close\s*\(\s*\)")
            if close_re.search(body) is not None:
                continue
            line = _line(text, body_offset + read.start())
            findings.append(
                _finding(
                    root_cause="http-response-body-read-without-close",
                    path=path,
                    line_start=line,
                    severity="major",
                    category="resource_lifecycle",
                    officer="Medic",
                    message="An owned HTTP response body is consumed without being closed.",
                    evidence=(
                        f"{function_name} receives `{response}` from a call, reads `{response}.Body`, and has no deferred or explicit body close in the function. "
                        "The connection resource can leak and normal keep-alive reuse can be prevented."
                    ),
                    falsifiers=(
                        "Checked that the function owns a newly returned response variable.",
                        "Checked that the response body is directly read or decoded in the same function.",
                        "Checked for deferred and explicit Body.Close calls across the function body.",
                        "Did not flag responses returned untouched to another owner.",
                    ),
                    verification=(
                        "Close the body immediately after successful response acquisition (normally with `defer` after the error check) and prove read, "
                        "decode and early-error paths all release the connection resource."
                    ),
                )
            )
            break
    return findings


def run_static_transfer_9_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
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
        findings.extend(_path_containment_findings(path, text))
        findings.extend(_interpreter_boundary_findings(path, text))
        findings.extend(_http_response_findings(path, text))

    unique = {(str(item["root_cause"]), str(item["path"])): item for item in findings}
    return {
        "schema_version": "sergeant.static-transfer-9-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
