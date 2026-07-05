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
INPUT_RE = re.compile(r"\b(req\.(?:body|query|params)|request\.(?:json|args|form)|input\(|process\.env)\b")
SINK_RE = re.compile(r"\b(eval|exec|subprocess|os\.system|innerHTML|dangerouslySetInnerHTML|raw\(|query\()\b")
N2_LOOP_RE = re.compile(r"\bfor\b[\s\S]{0,160}\bfor\b")
ASYNC_SHARED_RE = re.compile(r"\b(global|threading|asyncio\.create_task|Promise\.all|setTimeout|setInterval)\b")
API_KEYWORD_RE = re.compile(r"\b(api|route|client|server|handler|schema|contract|types?)\b", re.I)


@dataclass(frozen=True)
class CapabilityFinding:
    capability: CapabilityCategory
    severity: CapabilitySeverity
    message: str
    path: str | None = None
    evidence: str = ""
    confidence: float = 0.5
    related_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


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
    source_files = [file.path for file in insight.files if file.role in {"source", "ui", "database", "config", "infrastructure"}]
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
            findings.append(
                CapabilityFinding(
                    capability="cross_file",
                    severity="major" if len(dependents) >= 3 else "minor",
                    path=path,
                    message="Changed file has dependent modules that may be affected.",
                    evidence=f"{len(dependents)} dependent file(s) import this file.",
                    related_paths=dependents[:10],
                    confidence=0.76,
                )
            )
    return findings


def _architecture_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    imports: dict[str, set[str]] = indexes["imports"]
    for path in sorted(changed):
        if "/ui/" in f"/{path}" or path.startswith(("frontend/", "web/")):
            backend_deps = [dep for dep in imports.get(path, set()) if dep.startswith(("server/", "backend/", "api/"))]
            if backend_deps:
                findings.append(
                    CapabilityFinding(
                        capability="architecture",
                        severity="major",
                        path=path,
                        message="UI layer imports backend/server layer directly.",
                        evidence="Layer boundary appears crossed by imports.",
                        related_paths=backend_deps,
                        confidence=0.72,
                    )
                )
        if path.startswith(("src/", "app/")) and "test" in path.lower():
            continue
        if path.startswith(("scripts/", ".github/", "deploy/")):
            findings.append(
                CapabilityFinding(
                    capability="architecture",
                    severity="note",
                    path=path,
                    message="Infrastructure or automation path changed; review deployment impact.",
                    evidence="Path is in scripts, CI, or deployment surface.",
                    confidence=0.7,
                )
            )
    return findings


def _data_flow_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    for path in sorted(changed):
        text = indexes["texts"].get(path, "")
        if INPUT_RE.search(text) and SINK_RE.search(text):
            findings.append(
                CapabilityFinding(
                    capability="data_flow",
                    severity="major",
                    path=path,
                    message="User-controlled input appears near a risky sink.",
                    evidence="Input and sink patterns were both detected in the changed file.",
                    confidence=0.68,
                )
            )
    return findings


def _call_graph_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    exports: dict[str, set[str]] = indexes["exports"]
    calls: dict[str, set[str]] = indexes["calls"]
    changed_exports: dict[str, set[str]] = {path: exports.get(path, set()) for path in changed}
    for path, symbols in changed_exports.items():
        if not symbols:
            continue
        callers = []
        for other_path, other_calls in calls.items():
            if other_path == path:
                continue
            if symbols & other_calls:
                callers.append(other_path)
        if callers:
            findings.append(
                CapabilityFinding(
                    capability="call_graph",
                    severity="minor" if len(callers) < 5 else "major",
                    path=path,
                    message="Changed exported symbols are called from other files.",
                    evidence=f"Detected callers for exported symbols: {', '.join(sorted(symbols)[:5])}.",
                    related_paths=sorted(callers)[:10],
                    confidence=0.66,
                )
            )
    return findings


def _security_taint_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    for path in sorted(changed):
        text = indexes["texts"].get(path, "")
        if INPUT_RE.search(text) and re.search(r"\b(sql|query|exec|eval|shell|command)\b", text, re.I):
            findings.append(
                CapabilityFinding(
                    capability="security_taint",
                    severity="major",
                    path=path,
                    message="Potential tainted input path needs validation review.",
                    evidence="Input source and security-sensitive operation are both present.",
                    confidence=0.7,
                )
            )
    return findings


def _performance_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    for path in sorted(changed):
        text = indexes["texts"].get(path, "")
        if N2_LOOP_RE.search(text) or re.search(r"\.map\([^\)]*=>[\s\S]{0,120}\.map\(", text):
            findings.append(
                CapabilityFinding(
                    capability="performance",
                    severity="minor",
                    path=path,
                    message="Nested iteration pattern may create scaling risk.",
                    evidence="Nested loop/map pattern detected in changed file.",
                    confidence=0.62,
                )
            )
    return findings


def _concurrency_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    for path in sorted(changed):
        text = indexes["texts"].get(path, "")
        if ASYNC_SHARED_RE.search(text) and re.search(r"\b(cache|state|global|shared|counter)\b", text, re.I):
            findings.append(
                CapabilityFinding(
                    capability="concurrency",
                    severity="minor",
                    path=path,
                    message="Async or shared-state pattern may need race-condition review.",
                    evidence="Concurrent execution signal and shared state naming were both detected.",
                    confidence=0.6,
                )
            )
    return findings


def _api_contract_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    routes: dict[str, set[str]] = indexes["routes"]
    for path in sorted(changed):
        file_routes = routes.get(path, set())
        if file_routes:
            findings.append(
                CapabilityFinding(
                    capability="api_contract",
                    severity="major",
                    path=path,
                    message="API route contract changed or requires compatibility review.",
                    evidence=f"Detected routes: {', '.join(sorted(file_routes)[:5])}.",
                    confidence=0.74,
                )
            )
        elif API_KEYWORD_RE.search(path) and path.endswith((".ts", ".tsx", ".js", ".py", ".go", ".rs", ".java", ".cs")):
            findings.append(
                CapabilityFinding(
                    capability="api_contract",
                    severity="minor",
                    path=path,
                    message="API-adjacent file changed; check callers and contracts.",
                    evidence="Path name indicates API, route, client, schema, or contract surface.",
                    confidence=0.58,
                )
            )
    return findings


def _test_impact_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    insight = indexes["insight"]
    changed_non_tests = [path for path in changed if path not in insight.tests]
    changed_tests = [path for path in changed if path in insight.tests]
    if changed_non_tests and not changed_tests:
        return [
            CapabilityFinding(
                capability="test_impact",
                severity="major",
                message="Implementation changed without changed tests in the same PR.",
                evidence=f"Detected {len(changed_non_tests)} changed non-test file(s) and 0 changed test files.",
                related_paths=sorted(changed_non_tests)[:10],
                confidence=0.78,
            )
        ]
    return []


def _regression_findings(indexes: dict[str, Any], changed: set[str]) -> list[CapabilityFinding]:
    findings: list[CapabilityFinding] = []
    reverse_imports: dict[str, set[str]] = indexes["reverse_imports"]
    for path in sorted(changed):
        blast_radius = len(reverse_imports.get(path, set()))
        if blast_radius >= 5:
            findings.append(
                CapabilityFinding(
                    capability="regression",
                    severity="major",
                    path=path,
                    message="High blast-radius change may regress dependent behavior.",
                    evidence=f"At least {blast_radius} files depend on this file.",
                    related_paths=sorted(reverse_imports.get(path, set()))[:10],
                    confidence=0.72,
                )
            )
    return findings


def run_capability_engine(root: str | Path = ".", changed_files: list[str] | None = None) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = _changed_set(changed_files)
    indexes = _build_indexes(root_path)
    findings: list[CapabilityFinding] = []
    findings.extend(_cross_file_findings(indexes, changed))
    findings.extend(_architecture_findings(indexes, changed))
    findings.extend(_data_flow_findings(indexes, changed))
    findings.extend(_call_graph_findings(indexes, changed))
    findings.extend(_security_taint_findings(indexes, changed))
    findings.extend(_performance_findings(indexes, changed))
    findings.extend(_concurrency_findings(indexes, changed))
    findings.extend(_api_contract_findings(indexes, changed))
    findings.extend(_test_impact_findings(indexes, changed))
    findings.extend(_regression_findings(indexes, changed))

    covered = sorted({finding.capability for finding in findings})
    capability_status = {
        "cross_file": "active",
        "architecture": "active",
        "data_flow": "active",
        "call_graph": "active",
        "security_taint": "active",
        "performance": "active",
        "concurrency": "active",
        "api_contract": "active",
        "test_impact": "active",
        "regression": "active",
        "language": "scanner-backed",
    }
    severity_rank = {"blocker": 4, "major": 3, "minor": 2, "note": 1}
    strongest = max((severity_rank[finding.severity] for finding in findings), default=0)
    verdict = "BLOCK" if strongest == 4 else "NEEDS WORK" if strongest >= 3 else "PASS"
    return {
        "verdict": verdict,
        "changed_files": sorted(changed),
        "capability_status": capability_status,
        "covered_by_findings": covered,
        "finding_count": len(findings),
        "findings": [finding.to_dict() for finding in findings],
    }
