"""Static checks learned after transfer set 23's blind artifact was frozen."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable


_SOURCE_SUFFIXES = {".go", ".java", ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp"}


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
    officer: str,
    capability: str,
    category: str,
    severity: str,
    root_cause: str,
    path: str,
    line_start: int,
    message: str,
    evidence: str,
    falsifiers: list[str],
    verification: str,
    confidence: float,
    supporting: Iterable[str] = (),
) -> dict[str, Any]:
    primary = f"{path}:{line_start}"
    return {
        "source": "static-transfer-23-officer",
        "officer": officer,
        "capability": capability,
        "category": category,
        "severity": severity,
        "root_cause": root_cause,
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": primary,
        "supporting_evidence_refs": list(dict.fromkeys([primary, *supporting])),
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": falsifiers,
        "verification_test": verification,
        "confidence": confidence,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


_GO_FUNC_RE = re.compile(
    r"\bfunc\s+(?:\([^)]*\)\s*)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\((?P<params>[^)]*)\)[^{]*\{",
    re.M,
)


def _go_functions(text: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for match in _GO_FUNC_RE.finditer(text):
        opening = text.find("{", match.start(), match.end())
        closing = _matching_brace(text, opening) if opening >= 0 else None
        if closing is None:
            continue
        result.append(
            {
                "name": match.group("name"),
                "params": match.group("params"),
                "start": match.start(),
                "body_start": opening + 1,
                "body": text[opening + 1 : closing],
            }
        )
    return result


def _go_auth_helpers(functions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    helpers: dict[str, dict[str, Any]] = {}
    for function in functions:
        name = str(function["name"])
        params = str(function["params"])
        body = str(function["body"])
        if not re.search(r"(?:check|authorize|validate)[A-Za-z0-9_]*(?:Auth|Permission)", name, re.I):
            continue
        request_type = re.search(r"\*[^,)]*?(?P<operation>[A-Z][A-Za-z0-9_]*)Request\b", params)
        if request_type is None:
            continue
        operation = request_type.group("operation")
        direct = re.search(rf"\.Is{re.escape(operation)}Permitted\s*\(", body)
        if direct is None:
            continue
        extra_checks = re.findall(
            r"(?:\.Is[A-Za-z0-9_]+Permitted\s*\(|\bcheck[A-Za-z0-9_]+\s*\()",
            body,
        )
        if len(extra_checks) < 2:
            continue
        helpers[operation] = function
    return helpers


def _nested_auth_findings(path: str, text: str) -> list[dict[str, Any]]:
    functions = _go_functions(text)
    helpers = _go_auth_helpers(functions)
    if not helpers:
        return []

    findings: list[dict[str, Any]] = []
    for function in functions:
        body = str(function["body"])
        if "switch" not in body or "RequestOp_" not in body:
            continue
        for operation, helper in helpers.items():
            case = re.search(
                rf"case\s+\*[^:\n]*RequestOp_Request{re.escape(operation)}\s*:\s*"
                rf"(?P<body>[\s\S]*?)(?=\n\s*case\s+|\n\s*default\s*:|\Z)",
                body,
            )
            if case is None:
                continue
            segment = case.group("body")
            if re.search(rf"\b{re.escape(str(helper['name']))}\s*\(", segment):
                continue
            simplified = re.search(rf"\.Is{re.escape(operation)}Permitted\s*\(", segment)
            if simplified is None:
                continue
            absolute = int(function["body_start"]) + case.start("body") + simplified.start()
            findings.append(
                _finding(
                    officer="Challenger",
                    capability="authorization",
                    category="security",
                    severity="blocker",
                    root_cause="nested-operation-bypasses-canonical-authorization-helper",
                    path=path,
                    line_start=_line(text, absolute),
                    message="A nested operation uses a simplified permission check instead of the canonical side-effect-aware authorization helper.",
                    evidence=(
                        f"The composite dispatcher handles `{operation}` requests with a direct `Is{operation}Permitted` call, while canonical helper "
                        f"`{helper['name']}` performs additional authorization obligations for the same request type. Nested execution therefore drops "
                        "permissions associated with optional reads, leases, previous-value exposure, or other operation side effects."
                    ),
                    falsifiers=[
                        "Required a canonical operation-specific authorization helper for the same request type.",
                        "Required that helper to perform more than the direct primary permission check.",
                        "Required a composite/nested request dispatcher to call only the simplified primary check.",
                        "Excluded dispatchers that delegate to the canonical helper and operations whose canonical helper adds no extra obligation.",
                    ],
                    verification=(
                        f"Route nested `{operation}` operations through `{helper['name']}`, thread every dependency required by that helper through recursive "
                        "dispatch, and test optional side effects under principals that hold only the primary permission."
                    ),
                    confidence=0.99,
                    supporting=(f"{path}:{_line(text, int(helper['start']))}",),
                )
            )
    return findings


def _query_scope_findings(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    pattern = re.compile(
        r"getQueryString\s*\(\s*\)[\s\S]{0,500}?"
        r"UriComponentsBuilder\.fromUriString\s*\(\s*UrlUtils\.buildRequestUrl\s*\([^)]*\)\s*\)"
        r"[\s\S]{0,350}?getQueryParams\s*\(\s*\)[\s\S]{0,180}?containsKey\s*\(",
        re.M,
    )
    for match in pattern.finditer(text):
        findings.append(
            _finding(
                officer="Engineer",
                capability="api_contract",
                category="correctness",
                severity="major",
                root_cause="query-only-decision-parses-unrelated-full-request-url",
                path=path,
                line_start=_line(text, match.start()),
                message="A query-only decision parses the entire request URL, allowing unrelated path syntax to break query matching.",
                evidence=(
                    "The branch first proves that a query string exists and ultimately inspects only query parameters, yet it rebuilds and parses the "
                    "complete request URL. Invalid or newly strict syntax in the path, authority, or fragment can therefore fail an operation that does "
                    "not semantically depend on those components."
                ),
                falsifiers=[
                    "Required the decision to read `getQueryString()` and finish with query-parameter membership.",
                    "Required the parser input to be a rebuilt full request URL rather than the query component.",
                    "Excluded code that actually consumes path or authority from the parsed result.",
                    "Excluded query-only builders that receive `request.getQueryString()` directly.",
                ],
                verification=(
                    "Parse only the query component needed for the decision and test a valid query against request paths containing literal percent signs "
                    "or other syntax that is irrelevant to query matching."
                ),
                confidence=0.99,
            )
        )
    return findings


_BOOL_FIELD_RE = re.compile(
    r"(?:^|_)(?:is_|has_)?(?:allow|disallow|enable|enabled|disable|disabled|error|strict|optional|required)(?:_|$)",
    re.I,
)


def _wrapper_bool_findings(path: str, text: str) -> list[dict[str, Any]]:
    if "google/protobuf/wrappers.upb.h" not in text:
        return []
    assignments = re.finditer(
        r"(?P<target>[A-Za-z_][A-Za-z0-9_]*)\.(?P<field>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
        r"(?P<accessor>[a-z][A-Za-z0-9_]*_[A-Za-z0-9_]+)\s*\(\s*(?P<arg>[A-Za-z_][A-Za-z0-9_]*)\s*\)\s*;",
        text,
        re.M,
    )
    findings: list[dict[str, Any]] = []
    for match in assignments:
        field = match.group("field")
        accessor = match.group("accessor")
        if not _BOOL_FIELD_RE.search(f"_{field}_"):
            continue
        if not accessor.endswith(f"_{field}"):
            continue
        line_start = _line(text, match.start())
        findings.append(
            _finding(
                officer="Engineer",
                capability="api_contract",
                category="correctness",
                severity="major",
                root_cause="protobuf-bool-wrapper-presence-assigned-as-value",
                path=path,
                line_start=line_start,
                message="A generated protobuf BoolValue wrapper accessor is assigned directly to a primitive boolean.",
                evidence=(
                    f"Destination `{match.group('target')}.{field}` receives generated accessor `{accessor}(...)` directly in a parser that includes "
                    "protobuf wrapper support. Wrapper accessors return message pointers; implicit pointer-to-bool conversion reports presence, not the "
                    "contained value, so an explicitly configured false becomes true."
                ),
                falsifiers=[
                    "Required protobuf wrapper support in the parser translation unit.",
                    "Required a generated C-style accessor whose field suffix matches a boolean-semantic destination field.",
                    "Required direct assignment with no value-unwrapping helper, dereference, null-aware value extraction, or explicit comparison.",
                    "Excluded ordinary object methods, explicit wrapper parsing, and non-boolean destination fields.",
                ],
                verification=(
                    "Unwrap the BoolValue with the canonical helper or explicit null-aware `.value` accessor and test absent, explicit false, and explicit true."
                ),
                confidence=0.97,
            )
        )
    return findings


def run_static_transfer_23_review(
    root: str | Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
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
        if suffix == ".go":
            findings.extend(_nested_auth_findings(path, text))
        elif suffix == ".java":
            findings.extend(_query_scope_findings(path, text))
        else:
            findings.extend(_wrapper_bool_findings(path, text))

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[
            (
                str(finding.get("root_cause")),
                str(finding.get("path")),
                int(finding.get("line_start") or 0),
            )
        ] = finding

    return {
        "schema_version": "sergeant.static-transfer-23-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
