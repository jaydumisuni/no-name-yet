"""Static contract checks for UI persistence, response shape, and ambient runtime authority."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_SCRIPT_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}
_CPP_HEADER_SUFFIXES = {".h", ".hh", ".hpp", ".hxx"}
_CPP_SOURCE_SUFFIXES = {".cc", ".cpp", ".cxx"}


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
    message: str,
    evidence: str,
    falsifiers: Iterable[str],
    verification: str,
    supporting: Iterable[str] = (),
    confidence: float = 0.97,
) -> dict[str, Any]:
    refs = [f"{path}:{line_start}", *[str(item) for item in supporting]]
    return {
        "source": "static-contract-surface-officer",
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


def _script_functions(text: str) -> Iterable[tuple[str, str, int]]:
    patterns = (
        re.compile(
            r"\b(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?"
            r"\([^)]*\)\s*(?::\s*[^=]+)?=>\s*\{",
            re.M,
        ),
        re.compile(
            r"\b(?:async\s+)?function\s+(?P<name>[A-Za-z_$][\w$]*)\s*\([^)]*\)"
            r"\s*(?::\s*[^\{]+)?\{",
            re.M,
        ),
    )
    for pattern in patterns:
        for match in pattern.finditer(text):
            opening = match.end() - 1
            closing = _matching_brace(text, opening)
            if closing is not None:
                yield match.group("name"), text[opening + 1 : closing], match.start()


def _has_persistence_sink(body: str) -> bool:
    return bool(
        re.search(r"\bfetch\s*\(", body)
        or re.search(r"\baxios(?:\.[A-Za-z_$][\w$]*)?\s*\(", body)
        or re.search(
            r"(?:\b[A-Za-z_$][\w$]*(?:API|Api|Service|Client)|\bapi|\bclient|\bservice)"
            r"\s*\.\s*[A-Za-z_$][\w$]*(?:create|update|patch|put|post|save|persist|commit)"
            r"[A-Za-z0-9_$]*\s*\(",
            body,
            re.I,
        )
        or re.search(r"\.\s*(?:patch|put|post|upsert|insert)\s*\(", body, re.I)
    )


def _ui_persistence_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() not in _SCRIPT_SUFFIXES:
        return []
    findings: list[dict[str, Any]] = []
    for name, body, offset in _script_functions(text):
        if re.search(r"(?:save|commit|submit)", name, re.I) is None:
            continue
        setters = re.findall(r"\b(set[A-Z][A-Za-z0-9_$]*)\s*\(", body)
        if not setters:
            continue
        clears_editor = any(
            re.search(r"(?:edit|editing|draft|form|modal|open|saving)", setter, re.I)
            and re.search(rf"\b{re.escape(setter)}\s*\(\s*(?:null|false)\s*\)", body)
            for setter in setters
        )
        domain_setters = [
            setter
            for setter in setters
            if re.search(r"(?:edit|editing|draft|form|modal|open|saving|loading|error|selected)", setter, re.I)
            is None
        ]
        if not clears_editor or not domain_setters or _has_persistence_sink(body):
            continue
        line = _line(text, offset)
        findings.append(
            _finding(
                root_cause="ui-save-clears-edit-without-durable-persistence",
                path=path,
                line_start=line,
                severity="major",
                category="state_lifecycle",
                message="A user-facing save action updates only local UI state and exits edit mode without proving durable persistence.",
                evidence=(
                    f"`{name}` mutates domain state through {', '.join(sorted(set(domain_setters)))} "
                    "and clears edit/draft state, but its function body contains no API, HTTP, mutation, "
                    "or persistence sink."
                ),
                falsifiers=(
                    "Checked that the function is explicitly a save, submit, or commit action.",
                    "Checked that it mutates non-editor React state and then clears editor/draft state.",
                    "Checked the same function body for fetch, API-client, PATCH/PUT/POST, mutation, or persistence calls.",
                ),
                verification=(
                    "Persist the edited record first, fail loudly without leaving edit mode on non-success, "
                    "and update local state only after the durable write succeeds."
                ),
            )
        )
    return findings


def _dart_collection_contract_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() != ".dart":
        return []
    findings: list[dict[str, Any]] = []
    function_re = re.compile(
        r"Future\s*<\s*List\s*<[\s\S]{0,180}?>\s*>\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
        r"\s*\([^)]*\)\s*async\s*\{",
        re.M,
    )
    for function in function_re.finditer(text):
        opening = function.end() - 1
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        body = text[opening + 1 : closing]
        source = re.search(
            r"\bfinal\s+(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*await\s+"
            r"[\s\S]{0,300}?(?:get|fetch|request)\s*\(",
            body,
            re.I,
        )
        if source is None:
            continue
        variable = source.group("var")
        mismatch = re.search(
            rf"\bif\s*\(\s*{re.escape(variable)}\s+is!\s+List(?:\s*<[^>]+>)?\s*\)"
            rf"\s*(?:\{{\s*)?return\s*(?:<[^>]+>)?\s*\[\s*\]\s*;",
            body,
            re.M,
        )
        if mismatch is None:
            continue
        line = _line(text, opening + 1 + mismatch.start())
        findings.append(
            _finding(
                root_cause="malformed-collection-response-silently-treated-as-empty",
                path=path,
                line_start=line,
                severity="major",
                category="api_contract",
                message="A malformed collection response is converted into a valid empty-domain result.",
                evidence=(
                    f"`{function.group('name')}` receives `{variable}` from an awaited request and returns `[]` "
                    "when the response is not a List, hiding a response-contract failure as legitimate empty data."
                ),
                falsifiers=(
                    "Checked that the function contract returns a collection.",
                    "Checked that the tested value comes from an awaited request/fetch/get call.",
                    "Checked that a type mismatch returns an empty list instead of throwing a controlled contract error.",
                ),
                verification=(
                    "Reject unexpected response shapes with a controlled typed error while preserving valid empty lists "
                    "that arrive as an actual list payload."
                ),
            )
        )
    return findings


def _ambient_cpp_authority_findings(texts: dict[str, str]) -> list[dict[str, Any]]:
    headers = {path: text for path, text in texts.items() if Path(path).suffix.lower() in _CPP_HEADER_SUFFIXES}
    sources = {path: text for path, text in texts.items() if Path(path).suffix.lower() in _CPP_SOURCE_SUFFIXES}
    findings: list[dict[str, Any]] = []
    for header_path, header in headers.items():
        context = f"{header_path}\n{header}"
        if re.search(r"(?:registry|factory|command|router|dispatcher)", context, re.I) is None:
            continue
        for setter in re.finditer(
            r"\bstatic\s+void\s+set(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(\s*"
            r"(?P<type>[A-Za-z_][A-Za-z0-9_:]*)\s*\*\s*[A-Za-z_][A-Za-z0-9_]*\s*\)\s*;",
            header,
        ):
            name = setter.group("name")
            resource_type = setter.group("type")
            getter = re.search(
                rf"\bstatic\s+{re.escape(resource_type)}\s*\*\s*get{re.escape(name)}\s*\(\s*\)\s*;",
                header,
            )
            if getter is None:
                continue
            evidence_refs: list[str] = []
            source_match: tuple[str, str, int] | None = None
            for source_path, source in sources.items():
                pointer = re.search(
                    rf"\b{re.escape(resource_type)}\s*\*\s*(?P<var>s_[A-Za-z_][A-Za-z0-9_]*)\s*=\s*nullptr\s*;",
                    source,
                )
                if pointer is None:
                    continue
                variable = pointer.group("var")
                setter_impl = re.search(
                    rf"::set{re.escape(name)}\s*\([^)]*\)\s*\{{[\s\S]{{0,400}}?\b{re.escape(variable)}\s*=",
                    source,
                )
                getter_impl = re.search(
                    rf"::get{re.escape(name)}\s*\(\s*\)\s*\{{[\s\S]{{0,300}}?\breturn\s+{re.escape(variable)}\s*;",
                    source,
                )
                factory_use = re.search(
                    rf"(?:register(?:Command|Factory)|Factory|build)[\s\S]{{0,5000}}?\bget{re.escape(name)}\s*\(\s*\)",
                    source,
                    re.I,
                )
                if setter_impl and getter_impl and factory_use:
                    source_match = (source_path, source, pointer.start())
                    evidence_refs.extend(
                        [
                            f"{source_path}:{_line(source, pointer.start())}",
                            f"{source_path}:{_line(source, factory_use.start())}",
                        ]
                    )
                    break
            if source_match is None:
                continue
            source_path, _, _ = source_match
            line = _line(header, setter.start())
            findings.append(
                _finding(
                    root_cause="process-wide-mutable-runtime-authority-in-command-registry",
                    path=header_path,
                    line_start=line,
                    severity="major",
                    category="architecture",
                    message="A command/factory registry reaches live runtime authority through a process-wide mutable pointer.",
                    evidence=(
                        f"The registry exposes static `set{name}`/`get{name}` accessors for `{resource_type}*`; "
                        f"`{source_path}` stores that authority in namespace-scope mutable state and factories read it "
                        "ambiently instead of receiving per-build context."
                    ),
                    falsifiers=(
                        "Checked that both a static setter and getter expose a pointer-valued runtime dependency.",
                        "Checked that the implementation stores the dependency in namespace/process-wide mutable state.",
                        "Checked that registry/factory construction reads the getter rather than receiving explicit operation context.",
                    ),
                    verification=(
                        "Thread a narrow immutable build/command context through the factory signature, remove the global setter/getter, "
                        "and prove independent sessions cannot overwrite one another's runtime authority."
                    ),
                    supporting=evidence_refs,
                )
            )
    return findings


def run_static_contract_surface_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    texts = {path: _safe_text(root_path, path) for path in changed}
    texts = {path: text for path, text in texts.items() if text}

    findings: list[dict[str, Any]] = []
    for path, text in texts.items():
        findings.extend(_ui_persistence_findings(path, text))
        findings.extend(_dart_collection_contract_findings(path, text))
    findings.extend(_ambient_cpp_authority_findings(texts))

    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding.get("root_cause")), str(finding.get("path")))] = finding

    return {
        "schema_version": "sergeant.static-contract-surface-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "executed_project_code": False,
    }
