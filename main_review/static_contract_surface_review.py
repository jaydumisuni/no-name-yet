"""Canonical static review for UI persistence and ambient runtime authority."""

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
    category: str,
    message: str,
    evidence: str,
    falsifiers: Iterable[str],
    verification: str,
    supporting: Iterable[str] = (),
) -> dict[str, Any]:
    refs = [f"{path}:{line_start}", *[str(item) for item in supporting]]
    return {
        "source": "static-contract-surface-officer",
        "officer": "Engineer",
        "capability": category,
        "category": category,
        "severity": "major",
        "root_cause": root_cause,
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": refs[0],
        "supporting_evidence_refs": list(dict.fromkeys(refs)),
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": list(falsifiers),
        "verification_test": verification,
        "confidence": 0.97,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def _script_functions(text: str) -> Iterable[tuple[str, str, int]]:
    patterns = (
        re.compile(
            r"\b(?:const|let|var)\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*"
            r"(?:async\s*)?\([^)]*\)\s*(?::\s*[^=]+)?=>\s*\{",
            re.M,
        ),
        re.compile(
            r"\b(?:async\s+)?function\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)"
            r"\s*(?::\s*[^\{]+)?\{",
            re.M,
        ),
    )
    seen: set[tuple[int, str]] = set()
    for pattern in patterns:
        for match in pattern.finditer(text):
            key = (match.start(), match.group("name"))
            if key in seen:
                continue
            seen.add(key)
            opening = match.end() - 1
            closing = _matching_brace(text, opening)
            if closing is not None:
                yield match.group("name"), text[opening + 1 : closing], match.start()


def _has_persistence_boundary(body: str) -> bool:
    return bool(
        re.search(r"\b(?:fetch|authFetch)\s*\(", body)
        or re.search(r"\baxios(?:\.[A-Za-z_$][A-Za-z0-9_$]*)?\s*\(", body)
        or re.search(
            r"(?:\b[A-Za-z_$][A-Za-z0-9_$]*(?:API|Api|Service|Client)|\bapi|\bclient|\bservice)"
            r"\s*\.\s*[A-Za-z_$][A-Za-z0-9_$]*(?:create|update|patch|put|post|save|persist|commit)"
            r"[A-Za-z0-9_$]*\s*\(",
            body,
            re.I,
        )
        or re.search(r"\.\s*(?:patch|put|post|upsert|insert)\s*\(", body, re.I)
        or re.search(r"\b(?:onSave|onSubmit|persist|mutate|mutateAsync)\s*\(", body)
        or re.search(r"\b(?:localStorage|sessionStorage|indexedDB)\b", body)
    )


def _ui_state_only_save_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() not in _SCRIPT_SUFFIXES:
        return []

    findings: list[dict[str, Any]] = []
    for name, body, offset in _script_functions(text):
        if re.search(r"(?:save|submit|commit)", name, re.I) is None:
            continue
        setters = re.findall(r"\b(set[A-Z][A-Za-z0-9_$]*)\s*\(", body)
        if len(setters) < 2:
            continue
        domain_setters = [
            setter
            for setter in setters
            if re.search(r"(?:edit|editing|draft|form|modal|open|saving|loading|error|selected)", setter, re.I)
            is None
        ]
        clears_editor = any(
            re.search(r"(?:edit|editing|draft|form|modal|open|saving)", setter, re.I)
            and re.search(rf"\b{re.escape(setter)}\s*\(\s*(?:null|false)\s*\)", body)
            for setter in setters
        )
        if not domain_setters or not clears_editor or _has_persistence_boundary(body):
            continue
        findings.append(
            _finding(
                root_cause="ui-save-mutates-local-state-without-persistence",
                path=path,
                line_start=_line(text, offset),
                category="state_lifecycle",
                message="A user-facing save action updates local domain state and exits edit mode without proving durable persistence.",
                evidence=(
                    f"`{name}` updates {', '.join(sorted(set(domain_setters)))} and clears edit/draft state, but the handler contains no "
                    "request, API/client mutation, callback, durable browser storage, or other persistence boundary."
                ),
                falsifiers=(
                    "Checked that the function name represents save, submit, or commit intent.",
                    "Checked that domain state is changed and edit/draft state is cleared.",
                    "Checked the same function for HTTP/API/client mutations, save callbacks, and durable browser storage.",
                ),
                verification=(
                    "Persist first, surface non-success without leaving edit mode, and update local state only after the durable write succeeds. "
                    "Prove the edit survives refresh and failed writes remain recoverable."
                ),
            )
        )
    return findings


def _global_authority_findings(texts: dict[str, str]) -> list[dict[str, Any]]:
    headers = {path: text for path, text in texts.items() if Path(path).suffix.lower() in _CPP_HEADER_SUFFIXES}
    sources = {path: text for path, text in texts.items() if Path(path).suffix.lower() in _CPP_SOURCE_SUFFIXES}
    findings: list[dict[str, Any]] = []

    for header_path, header in headers.items():
        if re.search(r"(?:registry|factory|command|router|dispatcher)", f"{header_path}\n{header}", re.I) is None:
            continue
        for setter in re.finditer(
            r"\bstatic\s+void\s+set(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(\s*"
            r"(?P<type>[A-Za-z_][A-Za-z0-9_:]*)\s*\*\s*[A-Za-z_][A-Za-z0-9_]*\s*\)\s*;",
            header,
        ):
            name = setter.group("name")
            resource_type = setter.group("type")
            if re.search(
                rf"\bstatic\s+{re.escape(resource_type)}\s*\*\s*get{re.escape(name)}\s*\(\s*\)\s*;",
                header,
            ) is None:
                continue

            source_match: tuple[str, str, int, int] | None = None
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
                    source_match = (source_path, source, pointer.start(), factory_use.start())
                    break
            if source_match is None:
                continue

            source_path, source, pointer_offset, use_offset = source_match
            findings.append(
                _finding(
                    root_cause="process-wide-runtime-authority-reached-through-mutable-global",
                    path=header_path,
                    line_start=_line(header, setter.start()),
                    category="architecture",
                    message="A command/factory registry reaches operation-specific runtime authority through process-wide mutable state.",
                    evidence=(
                        f"The registry exposes static `set{name}`/`get{name}` accessors for `{resource_type}*`; `{source_path}` stores that "
                        "authority in a namespace-scope pointer and factories read it ambiently instead of receiving a per-build context."
                    ),
                    falsifiers=(
                        "Checked that both pointer-valued setter and getter accessors exist.",
                        "Checked that the implementation stores the dependency in process-wide mutable state.",
                        "Checked that a factory/build path consumes the getter rather than explicit operation context.",
                    ),
                    verification=(
                        "Thread a narrow request/session/build context through the factory signature, remove the global setter/getter, and prove "
                        "independent owners cannot overwrite or borrow one another's runtime dependency."
                    ),
                    supporting=(
                        f"{source_path}:{_line(source, pointer_offset)}",
                        f"{source_path}:{_line(source, use_offset)}",
                    ),
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
        findings.extend(_ui_state_only_save_findings(path, text))
    findings.extend(_global_authority_findings(texts))

    unique = {(str(item["root_cause"]), str(item["path"])): item for item in findings}
    return {
        "schema_version": "sergeant.static-contract-surface-review.v4",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": sorted(texts),
        "executed_project_code": False,
    }
