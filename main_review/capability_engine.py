"""Tier 1 capability engine for Sergeant.

The capability engine is static by design. It does not execute repository code.
It builds lightweight indexes that let Sergeant reason about a change set as a
system instead of a list of unrelated files.
"""

from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .scanner import scan_repository
from .static_invariant_review import run_static_invariant_review

CapabilitySeverity = Literal["blocker", "major", "minor", "note"]
CapabilityCategory = Literal[
    "cross_file",
    "architecture",
    "data_flow",
    "call_graph",
    "security_taint",
    "performance",
    "concurrency",
    "api_contract",
    "test_impact",
    "regression",
    "language",
]

IMPORT_RE = re.compile(r"^\s*(?:import\s+([\w./@-]+)|from\s+([\w.]+)\s+import\s+)")
JS_IMPORT_RE = re.compile(r"(?:import\s+.*?from\s+['\"]([^'\"]+)['\"]|require\(['\"]([^'\"]+)['\"]\))")
PY_CALL_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
JS_EXPORT_RE = re.compile(r"\bexport\s+(?:async\s+)?(?:function|const|class)\s+([A-Za-z_$][\w$]*)")
JS_FUNCTION_RE = re.compile(r"\b(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(")
HTTP_ROUTE_RE = re.compile(r"\b(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]")
INPUT_RE = re.compile(
    r"(?:\breq\.(?:body|query|params)\b|\brequest\.(?:json|args|form|params)\b|"
    r"\binput\s*\(|\bprocess\.env\b|\b(?:r|request)\.URL\.Query\(\)\.Get\s*\(|"
    r"\b(?:r|request)\.FormValue\s*\(|\b(?:c|ctx|context)\.(?:Query|Param|FormValue)\s*\(|"
    r"@(?:RequestParam|PathVariable)\b|\b(?:request|req)\.getParameter\s*\(|"
    r"\bparams\s*\[|\brequested\s*:\s*&(?:'\w+\s+)?str\b)",
    re.I,
)
SINK_RE = re.compile(
    r"(?:\beval\s*\(|\bexec\s*\(|\bsubprocess\.|\bos\.system\s*\(|"
    r"\bchild_process\.exec\s*\(|\bcp\.exec\s*\(|\binnerHTML\b|"
    r"\bdangerouslySetInnerHTML\b|\braw\s*\(|"
    r"\b(?:db|database|conn|connection|tx|stmt)\.(?:query|queryContext|execute|execContext)\s*\(|"
    r"(?<![.\w])(?:query|queryContext|execute|execContext)\s*\(|"
    r"\bRuntime\.getRuntime\(\)\.exec\s*\(|\bProcessBuilder\s*\(|\bProcess\.Start\s*\()",
    re.I,
)
N2_LOOP_RE = re.compile(r"\bfor\b[\s\S]{0,160}\bfor\b")
RUBY_EACH_DO_RE = re.compile(r"\.each\s+do\s+\|[^|]+\|", re.I)
RUBY_BLOCK_OPEN_RE = re.compile(
    r"^(?:class|module|def|if|unless|case|begin|while|until|for)\b|\bdo\s*(?:\|[^|]*\|)?\s*$",
    re.I,
)
RUBY_BLOCK_END_RE = re.compile(r"^end\b", re.I)
ASYNC_SHARED_RE = re.compile(
    r"(?:\bglobal\b|\bthreading\b|\basyncio\.create_task\b|\bPromise\.all\b|"
    r"\bsetTimeout\b|\bsetInterval\b|\basync\s+Task\b|\bTask\.(?:Run|Yield|WhenAll)\b|"
    r"\bgo\s+func\b|\btokio::spawn\b|\bThread\.new\b)",
    re.I,
)
SHARED_STATE_RE = re.compile(
    r"\b(?:global[A-Za-z0-9_]*|shared[A-Za-z0-9_]*|[A-Za-z0-9_]*(?:counter|cache|state))\b",
    re.I,
)
SHARED_MUTATION_RE = re.compile(
    r"\b(?:global[A-Za-z0-9_]*|shared[A-Za-z0-9_]*|[A-Za-z0-9_]*(?:counter|cache|state))"
    r"\s*(?:\+\+|--|[+\-*/]=)",
    re.I,
)
LOCK_BLOCK_RE = re.compile(r"\block\s*\([^)]*\)\s*$|\bsynchronized\b[^{}]*\)?\s*$", re.I)
CONTROL_BLOCK_RE = re.compile(r"^(?:if|for|foreach|while|switch|catch|using|lock|synchronized)\b", re.I)
LOCK_ACQUIRE_RE = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*\.(?:lock|wait|waitasync)\s*\(|"
    r"\bMonitor\.(?:Enter|TryEnter)\s*\(",
    re.I,
)
LOCK_RELEASE_RE = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*\.(?:unlock|release)\s*\(|"
    r"\bMonitor\.Exit\s*\(",
    re.I,
)
API_KEYWORD_RE = re.compile(r"\b(api|route|client|server|handler|schema|contract|types?)\b", re.I)
EVALUATION_PREFIXES = ("review-benchmarks/", "battle-tests/")


@dataclass(frozen=True)
class CapabilityFinding:
    capability: CapabilityCategory
    severity: CapabilitySeverity
    message: str
    path: str | None = None
    evidence: str = ""
    confidence: float = 0.5
    related_paths: list[str] = field(default_factory=list)
    line_start: int | None = None
    line_end: int | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        if self.line_start is None:
            payload.pop("line_start")
            payload.pop("line_end")
        elif self.line_end is None:
            payload["line_end"] = self.line_start
        return payload


def _is_evaluation_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    return normalized.startswith(EVALUATION_PREFIXES)


def _safe_read(root: Path, relative: str) -> str:
    try:
        return (root / relative).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _module_name(path: str) -> str:
    p = Path(path)
    if p.name == "__init__.py":
        return ".".join(part for part in p.parent.parts if part not in {"src", "lib", "app"})
    return ".".join(part for part in p.with_suffix("").parts if part not in {"src", "lib", "app"})


def _normalize_import(current: str, target: str) -> str:
    target = target.strip()
    if not target:
        return target
    if target.startswith("."):
        base = Path(current).parent.as_posix().replace("/", ".")
        return f"{base}.{target.lstrip('.')}",
    return target


def _resolve_import(import_name: str, module_index: dict[str, str]) -> str | None:
    candidates = [import_name, import_name.replace("/", ".")]
    for candidate in candidates:
        parts = candidate.split(".")
        while parts:
            key = ".".join(parts)
            if key in module_index:
                return module_index[key]
            parts.pop()
    return None


def _extract_python_symbols(text: str) -> tuple[set[str], set[str]]:
    exports: set[str] = set()
    calls: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return exports, calls
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            exports.add(node.name)
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.add(func.id)
            elif isinstance(func, ast.Attribute):
                calls.add(func.attr)
    return exports, calls


def _extract_text_symbols(path: str, text: str) -> tuple[set[str], set[str]]:
    if path.endswith(".py"):
        return _extract_python_symbols(text)
    exports = set(JS_EXPORT_RE.findall(text)) | set(JS_FUNCTION_RE.findall(text))
    calls = set(PY_CALL_RE.findall(text))
    return exports, calls


def _build_indexes(root: Path) -> dict[str, Any]:
    insight = scan_repository(root)
    source_files = [
        file.path
        for file in insight.files
        if file.role in {"source", "ui", "database", "config", "infrastructure"}
        and not _is_evaluation_path(file.path)
    ]
    module_index = {_module_name(path): path for path in source_files}
    imports: dict[str, set[str]] = {path: set() for path in source_files}
    reverse_imports: dict[str, set[str]] = {path: set() for path in source_files}
    exports: dict[str, set[str]] = {}
    calls: dict[str, set[str]] = {}
    routes: dict[str, set[str]] = {}
    texts: dict[str, str] = {}

    for path in source_files:
        text = _safe_read(root, path)
        texts[path] = text
        file_exports, file_calls = _extract_text_symbols(path, text)
        exports[path] = file_exports
        calls[path] = file_calls
        routes[path] = {f"{method.upper()} {route}" for method, route in HTTP_ROUTE_RE.findall(text)}
        found_imports: set[str] = set()
        for line in text.splitlines():
            match = IMPORT_RE.match(line)
            if match:
                found_imports.add(str(match.group(1) or match.group(2) or ""))
            for js_match in JS_IMPORT_RE.findall(line):
                found_imports.add(str(js_match[0] or js_match[1] or ""))
        for import_name in found_imports:
            normalized = _normalize_import(path, import_name)
            if isinstance(normalized, tuple):
                normalized = normalized[0]
            resolved = _resolve_import(normalized, module_index)
            if resolved and resolved != path:
                imports[path].add(resolved)
                reverse_imports.setdefault(resolved, set()).add(path)

    return {
        "insight": insight,
        "source_files": source_files,
        "imports": imports,
        "reverse_imports": reverse_imports,
        "exports": exports,
        "calls": calls,
        "routes": routes,
        "texts": texts,
    }


def _changed_set(changed_files: list[str] | None) -> set[str]:
    return {path.strip() for path in changed_files or [] if path.strip()}


def _cross_file_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    reverse_imports: dict[str, set[str]] = indexes["reverse_imports"]
    for path in sorted(changed):
        dependents = sorted(reverse_imports.get(path, set()))
        if dependents:
            findings.append(CapabilityFinding("cross_file", "major" if len(dependents) >= 3 else "minor", "Changed file has dependent modules that may be affected.", path, f"{len(dependents)} dependent file(s) import this file.", 0.76, dependents[:10]))
    return findings


def _architecture_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    imports: dict[str, set[str]] = indexes["imports"]
    for path in sorted(changed):
        if "/ui/" in f"/{path}" or path.startswith(("frontend/", "web/")):
            backend_deps = [dep for dep in imports.get(path, set()) if dep.startswith(("server/", "backend/", "api/"))]
            if backend_deps:
                findings.append(CapabilityFinding("architecture", "major", "UI layer imports backend/server layer directly.", path, "Layer boundary appears crossed by imports.", 0.72, backend_deps))
        if path.startswith(("src/", "app/")) and "test" in path.lower():
            continue
        if path.startswith(("scripts/", ".github/", "deploy/")):
            findings.append(CapabilityFinding("architecture", "note", "Infrastructure or automation path changed; review deployment impact.", path, "Path is in scripts, CI, or deployment surface.", 0.7))
    return findings


def _data_flow_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    return [CapabilityFinding("data_flow", "major", "User-controlled input appears near a risky sink.", path, "Input and sink patterns were both detected in the changed file.", 0.68) for path in sorted(changed) if INPUT_RE.search(indexes["texts"].get(path, "")) and SINK_RE.search(indexes["texts"].get(path, ""))]


def _call_graph_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    exports: dict[str, set[str]] = indexes["exports"]
    calls: dict[str, set[str]] = indexes["calls"]
    for path in sorted(changed):
        symbols = exports.get(path, set())
        callers = [other for other, other_calls in calls.items() if other != path and symbols & other_calls]
        if symbols and callers:
            findings.append(CapabilityFinding("call_graph", "minor" if len(callers) < 5 else "major", "Changed exported symbols are called from other files.", path, f"Detected callers for exported symbols: {', '.join(sorted(symbols)[:5])}.", 0.66, sorted(callers)[:10]))
    return findings


def _security_taint_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    return [CapabilityFinding("security_taint", "major", "Potential tainted input path needs validation review.", path, "Input source and security-sensitive operation are both present.", 0.7) for path in sorted(changed) if INPUT_RE.search(indexes["texts"].get(path, "")) and (SINK_RE.search(indexes["texts"].get(path, "")) or re.search(r"\b(sql|query|exec|eval|shell|command)\b", indexes["texts"].get(path, ""), re.I))]


def _has_nested_ruby_each(text: str) -> bool:
    """Recognize lexical Ruby block nesting without crossing a matching ``end``."""

    blocks: list[bool] = []
    for row in text.splitlines():
        code = row.split("#", 1)[0].strip()
        if not code:
            continue
        if RUBY_BLOCK_END_RE.match(code):
            if blocks:
                blocks.pop()
            continue
        each_block = bool(RUBY_EACH_DO_RE.search(code))
        if each_block and any(blocks):
            # Only an existing ``each do`` block establishes nested iteration;
            # class, method and conditional scopes merely preserve its lifetime.
            return True
        if each_block or RUBY_BLOCK_OPEN_RE.search(code):
            blocks.append(each_block)
    return False


def _brace_scopes(text: str) -> list[tuple[int, int]]:
    stack: list[int] = []
    scopes: list[tuple[int, int]] = []
    for position, character in enumerate(text):
        if character == "{":
            stack.append(position)
        elif character == "}" and stack:
            scopes.append((stack.pop(), position))
    return scopes


def _brace_header(text: str, opening: int) -> str:
    boundary = max(
        text.rfind("\n", 0, opening),
        text.rfind(";", 0, opening),
        text.rfind("{", 0, opening),
        text.rfind("}", 0, opening),
    )
    return text[boundary + 1:opening].strip()


def _mutation_is_guarded(text: str, mutation: re.Match[str], scopes: list[tuple[int, int]]) -> bool:
    containing = sorted(
        (scope for scope in scopes if scope[0] < mutation.start() < scope[1]),
        key=lambda scope: scope[1] - scope[0],
    )
    if any(LOCK_BLOCK_RE.search(_brace_header(text, opening)) for opening, _ in containing):
        return True

    # Imperative mutex APIs guard only the region after the most recent acquire
    # in the same enclosing function/block. Atomic operations are deliberately
    # excluded: one Interlocked call cannot protect another ``counter++``.
    function_scope = next(
        (
            scope
            for scope in containing
            if ")" in _brace_header(text, scope[0])
            and not CONTROL_BLOCK_RE.match(_brace_header(text, scope[0]))
        ),
        containing[0] if containing else (0, len(text)),
    )
    opening, _ = function_scope
    before = text[opening:mutation.start()]
    acquire_positions = [match.start() for match in LOCK_ACQUIRE_RE.finditer(before)]
    release_positions = [match.start() for match in LOCK_RELEASE_RE.finditer(before)]
    if acquire_positions and max(acquire_positions) > max(release_positions, default=-1):
        return True

    # Cover indentation-scoped Python/Ruby-style ``with lock`` constructs.
    lines = text[:mutation.start()].splitlines()
    mutation_indent = len(lines[-1]) - len(lines[-1].lstrip()) if lines else 0
    for row in reversed(lines[:-1]):
        if not row.strip():
            continue
        indent = len(row) - len(row.lstrip())
        if indent >= mutation_indent:
            continue
        if re.search(r"\bwith\s+[^:]*\b(?:lock|mutex|semaphore)\b[^:]*:\s*$", row, re.I):
            return True
        if indent == 0 or re.search(r"\b(?:def|function|func|Task|void|int)\b", row):
            break
    return False


def _first_unguarded_shared_mutation(text: str) -> re.Match[str] | None:
    scopes = _brace_scopes(text)
    return next(
        (
            mutation
            for mutation in SHARED_MUTATION_RE.finditer(text)
            if not _mutation_is_guarded(text, mutation, scopes)
        ),
        None,
    )


def _performance_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    return [CapabilityFinding("performance", "minor", "Nested iteration pattern may create scaling risk.", path, "Nested loop/map/each pattern detected in changed file.", 0.62) for path in sorted(changed) if N2_LOOP_RE.search(indexes["texts"].get(path, "")) or _has_nested_ruby_each(indexes["texts"].get(path, "")) or re.search(r"\.map\([^\)]*=>[\s\S]{0,120}\.map\(", indexes["texts"].get(path, ""))]


def _concurrency_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    for path in sorted(changed):
        text = indexes["texts"].get(path, "")
        mutation = _first_unguarded_shared_mutation(text)
        if (
            ASYNC_SHARED_RE.search(text)
            and SHARED_STATE_RE.search(text)
            and mutation is not None
        ):
            findings.append(CapabilityFinding(
                "concurrency",
                "minor",
                "Concurrent work mutates shared state without a visible synchronization guard.",
                path,
                "Concurrent execution, a shared-state mutation, and no atomic/lock guard were detected.",
                0.72,
                line_start=text[:mutation.start()].count("\n") + 1,
            ))
    return findings


def _api_contract_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    for path in sorted(changed):
        routes = indexes["routes"].get(path, set())
        if routes:
            findings.append(CapabilityFinding("api_contract", "major", "API route contract changed or requires compatibility review.", path, f"Detected routes: {', '.join(sorted(routes)[:5])}.", 0.74))
        elif API_KEYWORD_RE.search(path) and path.endswith((".ts", ".tsx", ".js", ".py", ".go", ".rs", ".java", ".cs")):
            findings.append(CapabilityFinding("api_contract", "minor", "API-adjacent file changed; check callers and contracts.", path, "Path name indicates API, route, client, schema, or contract surface.", 0.58))
    return findings


def _test_impact_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    insight = indexes["insight"]
    changed_non_tests = [path for path in changed if path not in insight.tests]
    changed_tests = [path for path in changed if path in insight.tests]
    if changed_non_tests and not changed_tests:
        return [CapabilityFinding("test_impact", "major", "Implementation changed without changed tests in the same PR.", evidence=f"Detected {len(changed_non_tests)} changed non-test file(s) and 0 changed test files.", confidence=0.78, related_paths=sorted(changed_non_tests)[:10])]
    return []


def _regression_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    for path in sorted(changed):
        dependents = sorted(indexes["reverse_imports"].get(path, set()))
        if len(dependents) >= 5:
            findings.append(CapabilityFinding("regression", "major", "High blast-radius change may regress dependent behavior.", path, f"At least {len(dependents)} files depend on this file.", 0.72, dependents[:10]))
    return findings


def _finding_identity(finding: dict[str, Any]) -> tuple[str, str, int, str]:
    return (
        str(finding.get("root_cause") or finding.get("message") or "unknown"),
        str(finding.get("path") or ""),
        int(finding.get("line_start") or 0),
        str(finding.get("message") or ""),
    )


def run_capability_engine(root: str | Path = ".", changed_files: list[str] | None = None) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = _changed_set(changed_files)
    evaluation_files = sorted(path for path in changed if _is_evaluation_path(path))
    reviewable_changed = changed - set(evaluation_files)
    indexes = _build_indexes(root_path)
    base_findings: list[CapabilityFinding] = []
    for provider in (
        _cross_file_findings,
        _architecture_findings,
        _data_flow_findings,
        _call_graph_findings,
        _security_taint_findings,
        _performance_findings,
        _concurrency_findings,
        _api_contract_findings,
        _test_impact_findings,
        _regression_findings,
    ):
        base_findings.extend(provider(indexes, reviewable_changed))

    invariant_review = run_static_invariant_review(root_path, sorted(reviewable_changed))
    finding_rows: list[dict[str, Any]] = [finding.to_dict() for finding in base_findings]
    finding_rows.extend(
        dict(item)
        for item in invariant_review.get("findings", [])
        if isinstance(item, dict)
    )

    severity_rank = {"blocker": 4, "major": 3, "minor": 2, "note": 1, "advisory": 1}
    unique: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    for finding in finding_rows:
        key = _finding_identity(finding)
        existing = unique.get(key)
        if existing is None:
            unique[key] = finding
            continue
        existing_score = (
            severity_rank.get(str(existing.get("severity") or "").lower(), 0),
            float(existing.get("confidence") or 0.0),
        )
        candidate_score = (
            severity_rank.get(str(finding.get("severity") or "").lower(), 0),
            float(finding.get("confidence") or 0.0),
        )
        if candidate_score > existing_score:
            unique[key] = finding

    findings = list(unique.values())
    covered = sorted(
        {
            str(finding.get("capability") or finding.get("category"))
            for finding in findings
            if str(finding.get("capability") or finding.get("category") or "")
        }
    )
    capability_status = {
        name: "active"
        for name in (
            "cross_file",
            "architecture",
            "data_flow",
            "call_graph",
            "security_taint",
            "performance",
            "concurrency",
            "api_contract",
            "test_impact",
            "regression",
        )
    }
    capability_status["language"] = "scanner-backed"
    for capability in covered:
        capability_status.setdefault(capability, "static-officer")

    strongest = max(
        (severity_rank.get(str(finding.get("severity") or "").lower(), 0) for finding in findings),
        default=0,
    )
    return {
        "verdict": "BLOCK" if strongest == 4 else "NEEDS WORK" if strongest >= 3 else "PASS",
        "changed_files": sorted(changed),
        "reviewable_changed_files": sorted(reviewable_changed),
        "evaluation_files_excluded": evaluation_files,
        "capability_status": capability_status,
        "covered_by_findings": covered,
        "finding_count": len(findings),
        "findings": findings,
        "static_invariant_review": invariant_review,
    }
