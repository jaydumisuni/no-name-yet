"""Static checks learned only after transfer set 20's blind artifact was frozen."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Iterable

_TS_SUFFIXES = {".ts", ".tsx", ".js", ".jsx"}


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
        if char in {'"', "'", "`"}:
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
    category: str,
    severity: str,
    message: str,
    evidence: str,
    falsifiers: Iterable[str],
    verification: str,
    supporting: Iterable[str] = (),
    confidence: float = 0.97,
) -> dict[str, Any]:
    refs = [f"{path}:{line_start}", *[str(item) for item in supporting]]
    return {
        "source": "static-transfer-20-officer",
        "officer": "Engineer",
        "capability": category,
        "category": category,
        "severity": severity,
        "root_cause": root_cause,
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": f"{path}:{line_start}",
        "supporting_evidence_refs": list(dict.fromkeys(refs)),
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": list(falsifiers),
        "verification_test": verification,
        "confidence": confidence,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def _python_hash_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() != ".py":
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    findings: list[dict[str, Any]] = []
    for class_node in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
        declared_fields: set[str] = set()
        for node in class_node.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                declared_fields.add(node.target.id)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__init__":
                for child in ast.walk(node):
                    if (
                        isinstance(child, (ast.Assign, ast.AnnAssign))
                        and isinstance(getattr(child, "target", None), ast.Attribute)
                        and isinstance(child.target.value, ast.Name)
                        and child.target.value.id == "self"
                    ):
                        declared_fields.add(child.target.attr)
                    elif isinstance(child, ast.Assign):
                        for target in child.targets:
                            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                                declared_fields.add(target.attr)

        for method in class_node.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) or method.name != "__hash__":
                continue
            for node in ast.walk(method):
                if not isinstance(node, ast.Return) or not isinstance(node.value, ast.Call):
                    continue
                outer = node.value
                if not isinstance(outer.func, ast.Name) or outer.func.id != "hash" or len(outer.args) != 1:
                    continue
                inner = outer.args[0]
                if not isinstance(inner, ast.Call) or not isinstance(inner.func, ast.Name) or inner.func.id != "type" or len(inner.args) != 1:
                    continue
                candidate = inner.args[0]
                if not (
                    isinstance(candidate, ast.Attribute)
                    and isinstance(candidate.value, ast.Name)
                    and candidate.value.id == "self"
                ):
                    continue
                field = candidate.attr
                if declared_fields and field not in declared_fields:
                    continue
                findings.append(
                    _finding(
                        root_cause="hash-contract-collapses-field-values-to-runtime-type",
                        path=path,
                        line_start=int(getattr(node, "lineno", getattr(method, "lineno", 1))),
                        category="correctness",
                        severity="major",
                        message="A value object's hash uses the runtime type of a field instead of the field value, collapsing distinct values into the same hash behavior.",
                        evidence=(
                            f"`{class_node.name}.__hash__` returns `hash(type(self.{field}))`. Distinct values sharing the same runtime "
                            "type therefore produce the same hash even when equality or behavior distinguishes those values."
                        ),
                        falsifiers=(
                            "Required a class `__hash__` method calling `hash(type(self.<field>))`.",
                            "Excluded `hash(type(self))`, class-identity hashes and direct value hashes.",
                            "Checked that the attribute is declared or initialized as instance state when declarations are available.",
                        ),
                        verification=(
                            f"Hash `self.{field}` or another equality-consistent immutable projection and prove unequal same-type values "
                            "do not collapse solely because their runtime types match."
                        ),
                        confidence=0.99,
                    )
                )
    return findings


def _rust_functions(text: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"(?m)^[ \t]*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<params>[\s\S]*?)\)\s*(?:->[^\{]+)?\{"
    )
    functions: list[dict[str, Any]] = []
    for match in pattern.finditer(text):
        opening = text.find("{", match.start())
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        functions.append(
            {
                "name": match.group("name"),
                "params": match.group("params"),
                "body": text[opening + 1 : closing],
                "start": match.start(),
                "body_start": opening + 1,
            }
        )
    return functions


def _rust_shared_compatibility_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() != ".rs":
        return []
    functions = _rust_functions(text)
    findings: list[dict[str, Any]] = []
    for helper in functions:
        params = str(helper["params"])
        body = str(helper["body"])
        if not re.search(r"type_?vars?|TypeVar|type_params?", params, re.I):
            continue
        if not re.search(r"report_diagnostic|Diagnostic|set_fix|diagnostic", body, re.I):
            continue
        if re.search(r"default\.is_some\s*\(\)", body):
            continue

        callers: list[dict[str, Any]] = []
        call_re = re.compile(rf"\b{re.escape(str(helper['name']))}\s*\(")
        for function in functions:
            if function is helper:
                continue
            if call_re.search(str(function["body"])):
                callers.append(function)
        if len(callers) < 2:
            continue

        guarded = [function for function in callers if re.search(r"default\.is_some\s*\(\)", str(function["body"]))]
        unguarded = [function for function in callers if function not in guarded]
        if not guarded or not unguarded:
            continue
        combined = "\n".join(str(function["body"]) for function in callers)
        if not re.search(r"target_version|PythonVersion|preview|enabled\s*\(", combined, re.I):
            continue

        guarded_function = guarded[0]
        unguarded_function = unguarded[0]
        line_start = _line(text, int(helper["start"]))
        findings.append(
            _finding(
                root_cause="compatibility-guard-applied-to-only-one-shared-diagnostic-path",
                path=path,
                line_start=line_start,
                category="api_contract",
                severity="major",
                message="A compatibility guard for default-bearing type parameters is applied in only one caller instead of the shared diagnostic path used by multiple entry points.",
                evidence=(
                    f"`{helper['name']}` is called by multiple rule entry points. `{guarded_function['name']}` checks default-bearing "
                    f"type parameters, while `{unguarded_function['name']}` reaches the same diagnostic without that guard, and the "
                    "shared helper contains no equivalent check. Backported syntax or feature/version combinations can therefore be "
                    "reported inconsistently across equivalent forms."
                ),
                falsifiers=(
                    "Required at least two entry functions calling the same diagnostic helper.",
                    "Required a default-bearing type-parameter guard in one caller and no equivalent guard in another.",
                    "Checked that the shared helper itself does not enforce the compatibility condition.",
                    "Required version, preview or feature-enable evidence in the surrounding rule implementation.",
                ),
                verification=(
                    "Move the version/feature/default compatibility decision into the shared diagnostic path and test every entry form "
                    "against native and backported syntax across supported target versions."
                ),
                supporting=(
                    f"{path}:{_line(text, int(guarded_function['start']))}",
                    f"{path}:{_line(text, int(unguarded_function['start']))}",
                ),
                confidence=0.97,
            )
        )
    return findings


def _typescript_sidecar_identity_findings(files: dict[str, str]) -> list[dict[str, Any]]:
    feature_paths = [path for path, text in files.items() if re.search(r"chunkImportMap|import\s*map", text, re.I)]
    if not feature_paths:
        return []

    map_provider: tuple[str, str] | None = None
    for path, text in files.items():
        if Path(path).suffix.lower() not in _TS_SUFFIXES:
            continue
        if re.search(r"function\s+getImportMap\b|const\s+getImportMap\b", text) and "content.imports" in text:
            map_provider = (path, text)
            break
    if map_provider is None:
        return []
    map_path, map_text = map_provider
    returns_mutable_content = bool(re.search(r"return\s*\{[^}]*\bcontent\b[^}]*\}", map_text, re.S))

    findings: list[dict[str, Any]] = []
    for path, text in files.items():
        if Path(path).suffix.lower() not in _TS_SUFFIXES or path == map_path:
            continue
        if not re.search(r"\bCSS\b|\bcss\b", text):
            continue
        emission = re.search(r"emitFile\s*\(\s*\{[\s\S]{0,800}?type\s*:\s*['\"]asset['\"]", text)
        if emission is None:
            continue
        chunk_link = re.search(r"chunk\.(?:fileName|preliminaryFileName)|RenderedChunk|chunkCSS", text)
        if chunk_link is None:
            continue
        tracks_reference = bool(re.search(r"chunkCssReferences|cssReferences|Map\s*<[^>]*>\s*\(\)|\.set\s*\(\s*chunk\.(?:fileName|preliminaryFileName)", text))
        updates_mapping = bool(re.search(r"content\.imports\s*\[|\.imports\s*\[", text))
        if returns_mutable_content and tracks_reference and updates_mapping:
            continue
        line_start = _line(text, emission.start())
        findings.append(
            _finding(
                root_cause="stable-chunk-identity-omits-emitted-css-sidecars",
                path=path,
                line_start=line_start,
                category="api_contract",
                severity="major",
                message="Stable import-map identities cover primary chunks but omit extracted CSS sidecars, allowing cached preload metadata to point at changed content-hashed assets.",
                evidence=(
                    "The build owns an import-map feature and emits CSS assets associated with rendered chunks, but the CSS emission path "
                    "does not retain the emitted reference and publish a stable CSS identity into the mutable import-map content. A CSS-only "
                    "change can therefore preserve the parent chunk identity while changing the preload dependency filename."
                ),
                falsifiers=(
                    "Required an import-map provider parsing `content.imports`.",
                    "Required per-chunk CSS asset emission in a separate build path.",
                    "Checked for retained chunk-to-CSS references and an import-map write for the sidecar.",
                    "Checked whether the import-map helper exposes mutable content to the sidecar producer.",
                ),
                verification=(
                    "Track each emitted CSS reference by originating chunk, derive a stable sidecar specifier from the chunk's stable identity, "
                    "write that mapping into the import map, and prove CSS-only rebuilds keep preload identities resolvable."
                ),
                supporting=(
                    f"{map_path}:{_line(map_text, map_text.find('function getImportMap') if 'function getImportMap' in map_text else 0)}",
                ),
                confidence=0.96,
            )
        )
    return findings


def run_static_transfer_20_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    findings: list[dict[str, Any]] = []
    texts: dict[str, str] = {}
    for path in changed:
        text = _safe_text(root_path, path)
        if not text:
            continue
        texts[path] = text
        findings.extend(_python_hash_findings(path, text))
        findings.extend(_rust_shared_compatibility_findings(path, text))
    findings.extend(_typescript_sidecar_identity_findings(texts))

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding.get("root_cause")), str(finding.get("path")), int(finding.get("line_start") or 0))] = finding

    return {
        "schema_version": "sergeant.static-transfer-20-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "executed_project_code": False,
    }
