"""Evidence-aware policy normalization for Tier 1 capability findings.

Capability scanners intentionally over-collect signals. This layer separates
blast radius and lexical co-presence from demonstrated defects, adds precise
source locations when available, recognizes specific safe guards, and augments
raw findings only when changed-source evidence proves a known risk shape.
"""
from __future__ import annotations

import ast
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .languages import classify_role

IMPACT_ONLY_CAPABILITIES = {"call_graph", "cross_file"}
EVALUATION_PREFIXES = ("review-benchmarks/", "battle-tests/")
SECURITY_SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".go", ".rs", ".java", ".kt", ".kts", ".c", ".cc", ".cpp",
    ".cs", ".php", ".rb", ".swift", ".sh", ".bash", ".ps1",
}
DEMONSTRATED_SECURITY_SINK_RE = re.compile(
    r"(?:\beval\s*\(|\bexec\s*\(|\bos\.system\s*\(|\bsubprocess\.|"
    r"\bchild_process\.exec\s*\(|\bcp\.exec\s*\(|"
    r"\b(?:db|database|conn|connection|tx|stmt)\.(?:query|queryContext|execute|execContext)\s*\(|"
    r"(?<![.\w])(?:query|queryContext|execute|execContext)\s*\(|"
    r"\braw\s*\(|\binnerHTML\b|\bdangerouslySetInnerHTML\b|\bshell\s*[:=]\s*true\b|"
    r"\bRuntime\.getRuntime\(\)\.exec\s*\(|\bProcessBuilder\s*\(|\bProcess\.Start\s*\(|"
    r"\b(?:std::)?fs::read\s*\(|\bFile::open\s*\(|\bFiles?\.(?:read|readAllBytes|open)\s*\()",
    re.I,
)
INPUT_SOURCE_RE = re.compile(
    r"(?:\breq\.(?:body|query|params)\b|\brequest\.(?:json|args|form|params)\b|"
    r"\binput\s*\(|\bprocess\.env\b|\b(?:r|request)\.URL\.Query\(\)\.Get\s*\(|"
    r"\b(?:r|request)\.FormValue\s*\(|\b(?:c|ctx|context)\.(?:Query|Param|FormValue)\s*\(|"
    r"@(?:RequestParam|PathVariable)\b|\b(?:request|req)\.getParameter\s*\(|"
    r"\bparams\s*\[|\brequested\s*:\s*&(?:'\w+\s+)?str\b)",
    re.I,
)
NON_QUERY_SENSITIVE_SINK_RE = re.compile(
    r"(?:\beval\s*\(|\bexec\s*\(|\bos\.system\s*\(|\bsubprocess\.|\bchild_process\.exec\s*\(|"
    r"\bcp\.exec\s*\(|\braw\s*\(|\binnerHTML\b|\bdangerouslySetInnerHTML\b|\bshell\s*[:=]\s*true\b|"
    r"\b(?:open|send_file|send_from_directory)\s*\(|\b(?:std::)?fs::read\s*\(|"
    r"\bFile::open\s*\(|\bFiles?\.(?:read|readAllBytes|open)\s*\(|"
    r"\bRuntime\.getRuntime\(\)\.exec\s*\(|\bProcessBuilder\s*\(|\bProcess\.Start\s*\()",
    re.I,
)
PARAMETERIZED_QUERY_RE = re.compile(
    r"\b(?:query|execute)\s*\(\s*([\"'])(?:(?!\1)[\s\S]){0,500}(?:\?|%s|\$\d+|:[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:(?!\1)[\s\S]){0,500}\1\s*,",
    re.I,
)
FILE_SINK_RE = re.compile(
    r"(?:\b(?:open|send_file|send_from_directory)\s*\(|\b(?:std::)?fs::read\s*\(|"
    r"\bFile::open\s*\(|\bFiles?\.(?:read|readAllBytes|open)\s*\()",
    re.I,
)
FILE_GUARD_RE = re.compile(
    r"\b(?:resolve|is_relative_to|secure_filename|basename|commonpath|normalize_repository_path)\b",
    re.I,
)
CANONICAL_PATH_RE = re.compile(r"\b(?:canonicalize|toRealPath|getCanonicalPath)\b", re.I)
CONTAINMENT_ASSERTION_RE = re.compile(
    r"\b(?:strip_prefix|starts_with|startsWith|is_relative_to|commonpath)\b",
    re.I,
)
PRIVILEGED_ROUTE_RE = re.compile(
    r"(?:\b(?:app|router)\.(?:get|post|put|patch|delete)\s*\(\s*[\"']/(?:admin|internal|manage|staff)(?:/|[\"'])|"
    r"@(?:Get|Post|Put|Patch|Delete|Request)Mapping\s*\(\s*(?:value\s*=\s*)?[\"']/(?:admin|internal|manage|staff)(?:/|[\"'])|"
    r"\[(?:HttpGet|HttpPost|HttpPut|HttpPatch|HttpDelete|Route)\s*\(\s*[\"']/(?:admin|internal|manage|staff)(?:/|[\"'])|"
    r"\b(?:get|post|put|patch|delete)\s+[\"']/(?:admin|internal|manage|staff)(?:/|[\"']))",
    re.I,
)
AUTH_GUARD_RE = re.compile(
    r"\b(?:authorize|authorization|permission|permissions|role|roles|is_admin|current_user|requires_role|"
    r"login_required|jwt|scope|scopes|auth_guard|PreAuthorize|Secured|Authorize|hasRole|hasAuthority)\b",
    re.I,
)
_LINE_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "security_taint": (FILE_SINK_RE, PRIVILEGED_ROUTE_RE, DEMONSTRATED_SECURITY_SINK_RE),
    "data_flow": (FILE_SINK_RE, DEMONSTRATED_SECURITY_SINK_RE),
    "performance": (re.compile(r"\bfor\b"), re.compile(r"\.map\s*\("), re.compile(r"\.each\s+do\b")),
    "concurrency": (
        re.compile(
            r"\b(?:global[A-Za-z0-9_]*|shared[A-Za-z0-9_]*|[A-Za-z0-9_]*(?:counter|cache|state))"
            r"\s*(?:\+\+|--|[+\-*/]=)",
            re.I,
        ),
        re.compile(r"\basyncio\.create_task\b|\bPromise\.all\b|\bsetTimeout\b|\bsetInterval\b"),
        re.compile(r"\bTask\.(?:Run|Yield|WhenAll)\b|\btokio::spawn\b|\bThread\.new\b", re.I),
    ),
    "api_contract": (re.compile(r"\b(?:app|router)\.(?:get|post|put|patch|delete)\s*\("),),
    "architecture": (re.compile(r"^\s*(?:from|import)\s+", re.M),),
}
_ROOT_CAUSES = {
    "security_taint": "unsafe-data-flow",
    "data_flow": "unsafe-data-flow",
    "api_contract": "change-impact",
    "regression": "change-impact",
    "cross_file": "change-impact",
    "call_graph": "change-impact",
    "test_impact": "proof-gap",
    "performance": "runtime-risk",
    "concurrency": "runtime-risk",
    "architecture": "architecture-boundary",
}


def _safe_text(root: Path | None, relative: object) -> str:
    if root is None or not isinstance(relative, str) or not relative:
        return ""
    try:
        resolved_root = root.resolve()
        path = (resolved_root / relative).resolve()
        if not path.is_relative_to(resolved_root) or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _is_evaluation_path(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    return normalized.startswith(EVALUATION_PREFIXES)


def _is_test_path(relative: str) -> bool:
    return classify_role(relative) == "test"


def _is_security_source_path(relative: str) -> bool:
    """Return whether source-to-sink rules can parse this file as executable code.

    Workflow/configuration files can contain embedded shell or Python snippets,
    but scanning their complete YAML/JSON text as one source program creates
    false request-to-file paths across unrelated steps. Those files remain in
    architecture and workflow assurance review; this rule only gates language-
    specific taint augmentation and verdict promotion.
    """

    return Path(relative.replace("\\", "/")).suffix.lower() in SECURITY_SOURCE_SUFFIXES


def _has_file_containment_guard(text: str) -> bool:
    if FILE_GUARD_RE.search(text):
        return True
    return bool(CANONICAL_PATH_RE.search(text) and CONTAINMENT_ASSERTION_RE.search(text))


def _nearby_input_and_file_sink(scope: str, *, maximum_distance: int = 1200) -> bool:
    sources = list(INPUT_SOURCE_RE.finditer(scope))
    sinks = list(FILE_SINK_RE.finditer(scope))
    return any(
        0 <= sink.start() - source.start() <= maximum_distance
        for source in sources
        for sink in sinks
    )


def _has_local_input_file_access(relative: str, text: str) -> bool:
    """Require request input and file access inside one bounded executable scope."""

    if Path(relative).suffix.lower() != ".py":
        return _nearby_input_and_file_sink(text)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _nearby_input_and_file_sink(text)
    lines = text.splitlines(keepends=True)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = getattr(node, "lineno", 1)
        end = getattr(node, "end_lineno", start)
        if _nearby_input_and_file_sink("".join(lines[start - 1:end])):
            return True
    return False


def _matching_brace(text: str, opening: int) -> int | None:
    depth = 0
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    index = opening
    while index < len(text):
        character = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if line_comment:
            if character == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if character == "*" and following == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            index += 1
            continue
        if character == "/" and following == "/":
            line_comment = True
            index += 2
            continue
        if character == "/" and following == "*":
            block_comment = True
            index += 2
            continue
        if character in {"'", '"', "`"}:
            quote = character
            index += 1
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _brace_function_scopes(text: str) -> list[str]:
    header = re.compile(
        r"(?:"
        r"func\s*(?:\([^)]*\)\s*)?[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\)\s*(?:\([^)]*\)|[^\{\n]+)?|"
        r"(?:export\s+)?(?:async\s+)?function\s+[A-Za-z_$][A-Za-z0-9_$]*\s*\([^)]*\)|"
        r"(?:export\s+)?(?:const|let|var)\s+[A-Za-z_$][A-Za-z0-9_$]*\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"
        r")\s*\{",
        re.M,
    )
    scopes: list[str] = []
    for match in header.finditer(text):
        opening = match.end() - 1
        closing = _matching_brace(text, opening)
        if closing is not None:
            scopes.append(text[opening + 1:closing])
    return scopes


def _scope_has_input_to_sensitive_sink(scope: str) -> bool:
    sinks = list(DEMONSTRATED_SECURITY_SINK_RE.finditer(scope))
    if not sinks or not INPUT_SOURCE_RE.search(scope):
        return False

    assignments: list[tuple[str, int]] = []
    assignment_re = re.compile(
        r"(?m)^\s*(?:(?:const|let|var)\s+)?(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*"
        r"(?::=|=)\s*(?P<value>[^\n;]+)"
    )
    for match in assignment_re.finditer(scope):
        if INPUT_SOURCE_RE.search(match.group("value")):
            assignments.append((match.group("name"), match.end()))

    for sink in sinks:
        sink_region = scope[sink.start(): min(len(scope), sink.start() + 700)]
        if INPUT_SOURCE_RE.search(sink_region):
            return True
        for name, assignment_end in assignments:
            if assignment_end <= sink.start() and re.search(rf"\b{re.escape(name)}\b", sink_region):
                return True
    return False


def _has_local_executable_sensitive_flow(relative: str, text: str) -> bool:
    suffix = Path(relative).suffix.lower()
    if suffix == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return False
        lines = text.splitlines(keepends=True)
        scopes = [
            "".join(lines[node.lineno - 1:(getattr(node, "end_lineno", None) or node.lineno)])
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
    else:
        scopes = _brace_function_scopes(text)
    return any(_scope_has_input_to_sensitive_sink(scope) for scope in scopes)


def _changed_test_covering_target(root: Path | None, changed_files: list[object], target: object) -> str:
    if root is None or not isinstance(target, str) or not target:
        return ""
    target_path = Path(target)
    target_stem = target_path.stem.lower()
    module_name = target.removesuffix(target_path.suffix).replace("/", ".").replace("\\", ".").lower()
    for item in changed_files:
        if not isinstance(item, str) or not _is_test_path(item):
            continue
        text = _safe_text(root, item).lower()
        if text and (module_name in text or target_stem in text):
            return item
    return ""


def _first_matching_line(text: str, patterns: tuple[re.Pattern[str], ...]) -> int | None:
    if not text:
        return None
    lines = text.splitlines()
    for pattern in patterns:
        for number, line in enumerate(lines, start=1):
            if pattern.search(line):
                return number
    return None


def _finding_exists(findings: list[object], capability: str, path: str, marker: str) -> bool:
    marker = marker.lower()
    return any(
        isinstance(item, dict)
        and item.get("capability") == capability
        and item.get("path") == path
        and marker in str(item.get("message") or "").lower()
        for item in findings
    )


def _augment_security_findings(
    findings: list[object],
    root: Path | None,
    changed_files: list[object],
) -> None:
    """Add high-confidence path and authorization findings from changed code."""

    if root is None:
        return
    for item in changed_files:
        if (
            not isinstance(item, str)
            or _is_test_path(item)
            or _is_evaluation_path(item)
            or not _is_security_source_path(item)
        ):
            continue
        text = _safe_text(root, item)
        if not text:
            continue

        if _has_local_input_file_access(item, text) and not _has_file_containment_guard(text):
            if not _finding_exists(findings, "data_flow", item, "file access"):
                findings.append({
                    "capability": "data_flow",
                    "severity": "major",
                    "path": item,
                    "message": "User-controlled path reaches file access without containment proof.",
                    "evidence": "Request input reaches file access and no resolve/commonpath/secure-filename containment guard was detected.",
                    "confidence": 0.84,
                    "root_cause": "unsafe-file-access",
                })
            if not _finding_exists(findings, "security_taint", item, "file access"):
                findings.append({
                    "capability": "security_taint",
                    "severity": "major",
                    "path": item,
                    "message": "Untrusted path input reaches file access without containment validation.",
                    "evidence": "No path-containment guard was detected before file access.",
                    "confidence": 0.87,
                    "root_cause": "unsafe-file-access",
                })

        if PRIVILEGED_ROUTE_RE.search(text) and not AUTH_GUARD_RE.search(text):
            if not _finding_exists(findings, "security_taint", item, "authorization guard"):
                findings.append({
                    "capability": "security_taint",
                    "severity": "major",
                    "path": item,
                    "message": "Privileged route lacks a visible authorization guard.",
                    "evidence": "An admin/internal/manage/staff route was detected without a role, permission, scope, authentication, or authorization guard.",
                    "confidence": 0.84,
                    "root_cause": "authorization-gap",
                })


def _root_cause_for(finding: dict[str, Any], capability: str) -> str:
    message = str(finding.get("message") or "").lower()
    if "authorization guard" in message:
        return "authorization-gap"
    if "file access" in message:
        return "unsafe-file-access"
    return _ROOT_CAUSES.get(capability, capability or "general-review")


def _annotate_location(finding: dict[str, Any], root: Path | None) -> str:
    text = _safe_text(root, finding.get("path"))
    capability = str(finding.get("capability") or "")
    finding.setdefault("root_cause", _root_cause_for(finding, capability))
    if not finding.get("line_start"):
        line = _first_matching_line(text, _LINE_PATTERNS.get(capability, ()))
        if line is not None:
            finding["line_start"] = line
            finding["line_end"] = line
    if finding.get("path") and finding.get("line_start"):
        finding["evidence_ref"] = f"{finding['path']}:{finding['line_start']}"
    finding["direct_evidence"] = bool(
        finding.get("evidence") and (finding.get("path") or capability == "test_impact")
    )
    return text


def normalize_capability_review(packet: dict[str, Any], root: str | Path | None = None) -> dict[str, Any]:
    """Return a capability packet with evidence-aware severity and location."""

    normalized = deepcopy(packet)
    raw_findings = normalized.get("findings", [])
    findings = raw_findings if isinstance(raw_findings, list) else []
    changed_files = normalized.get("changed_files", [])
    changed_files = changed_files if isinstance(changed_files, list) else []
    adjustments: list[dict[str, object]] = []
    root_path = Path(root) if root is not None else None
    _augment_security_findings(findings, root_path, changed_files)

    for finding in findings:
        if not isinstance(finding, dict):
            continue
        capability = str(finding.get("capability", ""))
        severity = str(finding.get("severity") or "unknown").lower()
        finding["severity"] = severity
        path = str(finding.get("path") or "")
        text = _annotate_location(finding, root_path)

        if (
            capability in {"data_flow", "security_taint"}
            and text
            and path
            and _has_local_executable_sensitive_flow(path, text)
        ):
            finding["executable_flow_proof"] = True
            finding["direct_evidence"] = True

        if capability in IMPACT_ONLY_CAPABILITIES and severity in {"blocker", "major"}:
            adjustments.append({
                "capability": capability,
                "path": finding.get("path"),
                "from": severity,
                "to": "minor",
                "reason": "Dependency or caller presence is blast-radius evidence, not a demonstrated defect.",
            })
            finding["severity"] = "minor"
            finding["impact_signal"] = True
            continue

        if capability in {"regression", "api_contract"} and severity in {"blocker", "major"}:
            coverage_path = _changed_test_covering_target(root_path, changed_files, finding.get("path"))
            if coverage_path:
                reason = (
                    "Blast radius remains review evidence, but the same change set includes focused changed-test coverage for the target module."
                    if capability == "regression"
                    else "The public contract surface remains review evidence, but focused changed-test coverage exists for the target module."
                )
                adjustments.append({
                    "capability": capability,
                    "path": finding.get("path"),
                    "from": severity,
                    "to": "minor",
                    "coverage_path": coverage_path,
                    "reason": reason,
                })
                finding["severity"] = "minor"
                finding["impact_signal"] = True
                finding["test_coverage_path"] = coverage_path
                finding["evidence"] = (
                    f"{finding.get('evidence', '')} Focused changed-test coverage: {coverage_path}.".strip()
                )
                continue

        if (
            capability in {"data_flow", "security_taint"}
            and severity in {"blocker", "major"}
            and path
            and not _is_security_source_path(path)
        ):
            adjustments.append({
                "capability": capability,
                "path": path,
                "from": severity,
                "to": "note",
                "reason": "Source-to-sink evidence came from a workflow or configuration file that this language-specific taint rule cannot parse as one executable program.",
            })
            finding["severity"] = "note"
            finding["configuration_signal"] = True
            finding["direct_evidence"] = False
            finding["message"] = "Workflow or configuration text contains source/sink terms; no executable data path was demonstrated."
            finding["evidence"] = "The scanner observed lexical source and sink patterns across a non-source file; workflow assurance remains authoritative."
            continue

        if capability in {"data_flow", "security_taint"} and severity in {"blocker", "major"}:
            if text and PARAMETERIZED_QUERY_RE.search(text) and not NON_QUERY_SENSITIVE_SINK_RE.search(text):
                adjustments.append({
                    "capability": capability,
                    "path": finding.get("path"),
                    "from": severity,
                    "to": "note",
                    "reason": "The query uses explicit parameter binding rather than interpolated request input.",
                })
                finding["severity"] = "note"
                finding["safe_binding_signal"] = True
                finding["direct_evidence"] = False
                continue

        if capability == "api_contract" and severity == "minor" and str(finding.get("message") or "").startswith("API-adjacent"):
            adjustments.append({
                "capability": capability,
                "path": finding.get("path"),
                "from": severity,
                "to": "note",
                "reason": "An API-adjacent filename is context, not a demonstrated contract change.",
            })
            finding["severity"] = "note"
            finding["context_signal"] = True
            finding["direct_evidence"] = False
            continue

        if capability == "security_taint" and severity in {"blocker", "major"}:
            explicit_security_evidence = finding.get("root_cause") in {"unsafe-file-access", "authorization-gap"}
            if text and not explicit_security_evidence and not DEMONSTRATED_SECURITY_SINK_RE.search(text):
                adjustments.append({
                    "capability": capability,
                    "path": finding.get("path"),
                    "from": severity,
                    "to": "note",
                    "reason": "Input and security-related words co-occur, but no executable sensitive sink was demonstrated.",
                })
                finding["severity"] = "note"
                finding["lexical_signal"] = True
                finding["direct_evidence"] = False
                finding["message"] = "Input and security-related configuration coexist; no direct sensitive sink was demonstrated."
                finding["evidence"] = "Static lexical scan found input and security terminology, but no executable sensitive sink."

    blockers = [item for item in findings if isinstance(item, dict) and item.get("severity") == "blocker"]
    majors = [item for item in findings if isinstance(item, dict) and item.get("severity") == "major"]
    normalized["verdict"] = "BLOCK" if blockers else "NEEDS WORK" if majors else "PASS"
    normalized["finding_count"] = len(findings)
    normalized["policy_adjustments"] = adjustments
    return normalized
