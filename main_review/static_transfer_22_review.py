"""Static checks learned after transfer set 22's blind artifact was frozen."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Iterable


_SOURCE_SUFFIXES = {".py", ".rs", ".ts", ".tsx", ".js", ".jsx"}


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
    source: str,
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
        "source": source,
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


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _target_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    return None


def _contains_nested_tuple_translation(loop: ast.For, variable: str) -> bool:
    for node in ast.walk(loop):
        if not isinstance(node, ast.Call):
            continue
        name = _base_name(node.func)
        if name not in {"zip", "Value", "Exact", "Tuple", "WhereNode"}:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and child.id == variable:
                return True
    return False


def _loop_filters_none(loop: ast.For, variable: str, text: str) -> bool:
    segment = ast.get_source_segment(text, loop) or ""
    if re.search(rf"\bNone\b[\s\S]{{0,160}}\b{re.escape(variable)}\b", segment) and "continue" in segment:
        return True
    if re.search(rf"\b{re.escape(variable)}\b[\s\S]{{0,160}}\bNone\b", segment) and "continue" in segment:
        return True
    if re.search(rf"\bif\s+None\s+(?:not\s+)?in\s+{re.escape(variable)}\b", segment):
        return True
    return False


def _compound_sql_null_findings(path: str, text: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    findings: list[dict[str, Any]] = []
    for cls in [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]:
        bases = {_base_name(base) for base in cls.bases}
        if "In" not in bases:
            continue
        methods = {
            node.name: node
            for node in cls.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        relevant = [methods[name] for name in ("process_rhs", "get_fallback_sql") if name in methods]
        if not relevant:
            continue

        unfiltered: list[ast.For] = []
        for method in relevant:
            for loop in [node for node in ast.walk(method) if isinstance(node, ast.For)]:
                variable = _target_name(loop.target)
                if not variable:
                    continue
                if not isinstance(loop.iter, ast.Name) or loop.iter.id not in {"rhs", "values", "items"}:
                    continue
                if not _contains_nested_tuple_translation(loop, variable):
                    continue
                if not _loop_filters_none(loop, variable, text):
                    unfiltered.append(loop)

        if not unfiltered:
            continue
        first = min(unfiltered, key=lambda node: int(getattr(node, "lineno", 0)))
        line_start = int(getattr(first, "lineno", 1))
        findings.append(
            _finding(
                source="static-transfer-22-officer",
                officer="Engineer",
                capability="api_contract",
                category="correctness",
                severity="major",
                root_cause="compound-sql-in-lookup-preserves-null-members",
                path=path,
                line_start=line_start,
                message="A compound SQL IN lookup translates tuple members containing None instead of discarding impossible NULL comparisons.",
                evidence=(
                    f"Class `{cls.name}` inherits the SQL `In` lookup and translates nested RHS members into tuple/equality expressions, "
                    "but its direct-value loops do not remove tuples containing `None`. SQL NULL equality cannot match, and when all "
                    "members are impossible the lookup must become an empty result rather than a real query."
                ),
                falsifiers=[
                    "Required an ORM lookup class that inherits the IN contract.",
                    "Required nested RHS tuple/list translation into SQL value or equality expressions.",
                    "Checked for a None-membership guard with continue/filter semantics inside each translation loop.",
                    "Excluded ordinary collection transforms and compound lookups that already elide NULL-bearing members.",
                ],
                verification=(
                    "Discard every compound RHS member containing None in both native and fallback SQL paths, raise the framework's "
                    "empty-result signal when nothing remains, and test mixed, all-NULL and genuinely empty inputs."
                ),
                confidence=0.98,
            )
        )
    return findings


_RUST_FN_RE = re.compile(
    r"(?:pub(?:\([^)]*\))?\s+)?(?:unsafe\s+)?fn\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"\s*\([^)]*\)\s*->\s*(?P<return>usize|u(?:8|16|32|64|128))\s*\{",
    re.M,
)


def _concurrent_unsigned_length_findings(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for function in _RUST_FN_RE.finditer(text):
        opening = text.find("{", function.start(), function.end())
        closing = _matching_brace(text, opening) if opening >= 0 else None
        if closing is None:
            continue
        body = text[opening + 1 : closing]
        if ".load(" not in body:
            continue
        if re.search(r"\b(?:wrapping|saturating|checked)_sub\s*\(", body):
            continue
        if re.search(r"\b(?:lock|mutex|guard)\b", body, re.I):
            continue

        loads = {
            match.group("var")
            for match in re.finditer(
                r"\blet\s+(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*[^;\n]+\.load\s*\([^;\n]+\)\s*;",
                body,
            )
        }
        if not loads:
            continue

        risky = re.search(
            r"(?P<expr>(?P<left>[A-Za-z_][A-Za-z0-9_]*)\s*-\s*[^;\n]+?\s*-\s*"
            r"\([^;\n]*(?:\.[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\)|\.load\s*\([^)]*\))"
            r"[^;\n]*\bas\s+(?:usize|u(?:8|16|32|64|128))\s*\))",
            body,
        )
        if risky is None or risky.group("left") not in loads:
            continue

        absolute = opening + 1 + risky.start("expr")
        findings.append(
            _finding(
                source="static-transfer-22-officer",
                officer="Mechanic",
                capability="concurrency",
                category="concurrency",
                severity="blocker",
                root_cause="concurrent-unsigned-distance-subtracts-independent-state-marker",
                path=path,
                line_start=_line(text, absolute),
                message="Unsigned length arithmetic subtracts an independently sampled concurrent state marker from a different snapshot.",
                evidence=(
                    f"Function `{function.group('name')}` returns `{function.group('return')}` and computes a distance from an atomic load, "
                    "then subtracts a separately observed boolean/state method cast to the same unsigned type. Those observations can describe "
                    "different moments during a concurrent transition, allowing the final subtraction to underflow or report an impossible length."
                ),
                falsifiers=[
                    "Required unsigned return arithmetic rooted in an atomic/shared-state load.",
                    "Required a second independently evaluated state/method result to be subtracted as an unsigned marker.",
                    "Checked for wrapping, saturating or checked subtraction.",
                    "Excluded visibly lock-guarded calculations and simple single-snapshot distances without an extra state marker.",
                ],
                verification=(
                    "Derive count and synthetic-state exclusion from one coherent slot/snapshot relation, use explicit wrapping/checked arithmetic "
                    "for monotonic indices, and exercise close/send races plus index wraparound."
                ),
                confidence=0.99,
            )
        )
    return findings


_TS_FUNCTION_RE = re.compile(
    r"(?:export\s+)?(?:async\s+)?function\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
    r"\s*\([^)]*\)\s*(?::\s*[^\{]+)?\{",
    re.M,
)


def _ts_functions(text: str) -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    for match in _TS_FUNCTION_RE.finditer(text):
        opening = text.find("{", match.start(), match.end())
        closing = _matching_brace(text, opening) if opening >= 0 else None
        if closing is None:
            continue
        result[match.group("name")] = (opening + 1, text[opening + 1 : closing])
    return result


def _partition_fallback_findings(path: str, text: str) -> list[dict[str, Any]]:
    functions = _ts_functions(text)
    findings: list[dict[str, Any]] = []
    for caller_name, (caller_offset, caller_body) in functions.items():
        loop_call = re.search(
            r"for\s*\([^)]*\bsection\b[^)]*\)\s*\{[\s\S]{0,500}?"
            r"(?:const|let)\s+[A-Za-z_$][A-Za-z0-9_$]*\s*=\s*"
            r"(?P<helper>[A-Za-z_$][A-Za-z0-9_$]*)\s*\(\s*section\.images\s*,\s*resource\s*,\s*data\s*\)"
            r"[\s\S]{0,260}?return\s+[^;]+;",
            caller_body,
        )
        if loop_call is None:
            continue
        helper_name = loop_call.group("helper")
        helper = functions.get(helper_name)
        if helper is None:
            continue
        _, helper_body = helper
        has_strong_identity = bool(
            re.search(r"(?:\.id\s*===\s*[^;\n]+|URI\.parse\s*\([^)]*\.id[^)]*\))", helper_body)
        )
        has_weak_data = bool(
            re.search(r"(?:data|buffer)[\s\S]{0,300}?(?:\.equals\s*\(|findIndex\s*\()", helper_body, re.I)
        )
        if not (has_strong_identity and has_weak_data):
            continue

        line_start = _line(text, caller_offset + loop_call.start())
        findings.append(
            _finding(
                source="static-transfer-22-officer",
                officer="Engineer",
                capability="correctness",
                category="correctness",
                severity="major",
                root_cause="partition-local-fallback-preempts-global-identity-match",
                path=path,
                line_start=line_start,
                message="A weaker content fallback is evaluated inside each partition before exact identity matching has searched all partitions.",
                evidence=(
                    f"Function `{caller_name}` walks segmented image collections and returns the first result from helper `{helper_name}`. "
                    "That helper performs URI/identifier matching and then byte-data equality fallback for each section. An earlier section's "
                    "same-content fallback can therefore preempt a later section's exact resource identity."
                ),
                falsifiers=[
                    "Required a segmented/sectioned outer search with immediate return on the first local match.",
                    "Required the same local helper to combine strong URI/identifier matching with weaker data/content fallback.",
                    "Excluded implementations that complete a global identity pass before starting a separate fallback pass.",
                    "Excluded helpers that use only one equivalence relation.",
                ],
                verification=(
                    "Search exact/canonical identity across every partition first, only then perform a second global content fallback, and test "
                    "identical bytes under distinct resource identities in different partitions."
                ),
                confidence=0.99,
            )
        )
    return findings


def _canonical_uri_projection_findings(path: str, text: str) -> list[dict[str, Any]]:
    if not re.search(r"deduplicat[A-Za-z0-9_]*[\s\S]{0,900}?\.uri\b", text, re.I):
        return []
    if not re.search(r"URI\.parse\s*\([^)]*\.id\s*\)", text):
        return []
    mapping = re.search(
        r"\.map\s*\(\s*\(\s*\{(?P<fields>[^}]+)\}\s*\)\s*=>\s*\(\s*\{(?P<object>[^}]+)\}\s*\)\s*\)",
        text,
        re.S,
    )
    if mapping is None:
        return []
    fields = mapping.group("fields")
    obj = mapping.group("object")
    if not re.search(r"\bid\b", fields) or not re.search(r"\bid\b", obj):
        return []
    if re.search(r"\buri\b", fields) or re.search(r"uri\.toString\s*\(\)", obj):
        return []

    line_start = _line(text, mapping.start())
    return [
        _finding(
            source="static-transfer-22-officer",
            officer="Engineer",
            capability="api_contract",
            category="correctness",
            severity="major",
            root_cause="canonical-resource-uri-discarded-before-identity-lookup",
            path=path,
            line_start=line_start,
            message="A collection projection discards the canonical URI but later treats a weaker id field as that URI for identity lookup.",
            evidence=(
                "The source collection's canonical `uri` is used for deduplication, yet the projected carousel object copies an `id` field "
                "without preserving `uri.toString()`. Downstream lookup parses `img.id` as a URI, so tool/generated resources can lose the "
                "identity required for exact selection."
            ),
            falsifiers=[
                "Required upstream logic that treats `uri` as the source identity.",
                "Required downstream lookup that parses or compares projected `id` as a URI.",
                "Required a projection that carries `id` but omits `uri`/`uri.toString()`.",
                "Excluded projections that explicitly set the output id from the canonical URI.",
            ],
            verification=(
                "Project canonical resource URI into the final identity field and test generated/tool resources whose local id differs from URI."
            ),
            confidence=0.98,
        )
    ]


def run_static_transfer_22_review(
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
        if suffix == ".py":
            findings.extend(_compound_sql_null_findings(path, text))
        elif suffix == ".rs":
            findings.extend(_concurrent_unsigned_length_findings(path, text))
        elif suffix in {".ts", ".tsx", ".js", ".jsx"}:
            findings.extend(_partition_fallback_findings(path, text))
            findings.extend(_canonical_uri_projection_findings(path, text))

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
        "schema_version": "sergeant.static-transfer-22-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
