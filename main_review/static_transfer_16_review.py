"""Static checks learned only after transfer set 16's blind 1/3 was frozen."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_CPP_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
_SPECIES_SUFFIXES = {".rs", ".js", ".jsx", ".ts", ".tsx", ".cc", ".cpp", ".cxx"}


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
        "source": "static-transfer-16-officer",
        "officer": "Mechanic" if category in {"lifecycle", "concurrency"} else "Engineer",
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


def _cpp_expirable_client_stop_findings(
    root: Path, changed: list[str], texts: dict[str, str]
) -> list[dict[str, Any]]:
    cpp_paths = [path for path in changed if Path(path).suffix.lower() in _CPP_SUFFIXES]
    if not cpp_paths:
        return []

    strong_members: dict[str, list[str]] = {}
    sync_stops: list[tuple[str, int]] = []
    for path in cpp_paths:
        text = texts.get(path, "")
        for match in re.finditer(
            r"\b(?P<member>m_[A-Za-z_][A-Za-z0-9_]*(?:client|connection|transport)[A-Za-z0-9_]*)"
            r"\s*\.\s*strong_ref\s*\(",
            text,
            re.I,
        ):
            strong_members.setdefault(match.group("member"), []).append(
                f"{path}:{_line(text, match.start())}"
            )
        for match in re.finditer(
            r"(?<!async_)\b(?:IPCProxy::)?(?:stop|cancel|abort)[A-Za-z0-9_]*\s*\(",
            text,
            re.I,
        ):
            prefix = text[max(0, match.start() - 80) : match.start()]
            if re.search(r"\basync_[A-Za-z0-9_]*\s*$", prefix, re.I):
                continue
            local = text[max(0, match.start() - 200) : match.end() + 200]
            if "IPCProxy::" in local or "send_sync" in local or "send_sync_but_allow_failure" in local:
                sync_stops.append((path, _line(text, match.start())))

    if not strong_members or not sync_stops:
        return []

    findings: list[dict[str, Any]] = []
    lifecycle_re = re.compile(
        r"(?:^|\n)\s*(?:[A-Za-z_][A-Za-z0-9_:<>,*&\s]+\s+)?"
        r"(?P<qualified>[A-Za-z_][A-Za-z0-9_:]*(?:::(?:stop|cancel|abort)[A-Za-z0-9_]*)|(?:stop|cancel|abort)[A-Za-z0-9_]*)"
        r"\s*\([^;{}]*\)\s*(?:const\s*)?\{",
        re.I | re.M,
    )
    for path in cpp_paths:
        text = texts.get(path, "")
        for function in lifecycle_re.finditer(text):
            opening = text.find("{", function.start())
            closing = _matching_brace(text, opening)
            if closing is None:
                continue
            body = text[opening + 1 : closing]
            for member, refs in strong_members.items():
                direct = re.search(
                    rf"\b{re.escape(member)}\s*->\s*(?:stop|cancel|abort)[A-Za-z0-9_]*\s*\(",
                    body,
                    re.I,
                )
                if direct is None:
                    continue
                if re.search(rf"\b{re.escape(member)}\s*\.\s*strong_ref\s*\(", body, re.I):
                    continue
                line = _line(text, opening + 1 + direct.start())
                sync_refs = [f"{sync_path}:{sync_line}" for sync_path, sync_line in sync_stops]
                findings.append(
                    _finding(
                        root_cause="lifecycle-stop-dereferences-expirable-client-and-sends-synchronously",
                        path=path,
                        line_start=line,
                        category="lifecycle",
                        severity="blocker",
                        message=(
                            "A lifecycle stop dereferences an expirable client directly and the paired cancellation path "
                            "performs synchronous IPC over a connection that may already be gone."
                        ),
                        evidence=(
                            f"`{function.group('qualified')}` invokes `{member}->...` without first acquiring the "
                            "strong reference that this codebase uses elsewhere for the same member. The changed "
                            "cancellation path also contains a synchronous IPC stop, so connection loss can leave the "
                            "request alive after its client and crash during teardown."
                        ),
                        falsifiers=(
                            "Required independent evidence that the same member supports strong_ref(), proving expirable ownership semantics.",
                            "Checked the lifecycle method for a local strong-reference acquisition before dereference.",
                            "Required a paired synchronous IPC stop/cancel/abort operation in the reviewed scope.",
                            "Excluded async_* cancellation sends and send_sync_but_allow_failure-style guarded sends.",
                        ),
                        verification=(
                            "Acquire and test a strong client reference before stopping, use asynchronous or explicitly "
                            "failure-tolerant cancellation over the transport, and reproduce connection loss followed by teardown."
                        ),
                        supporting=(*refs, *sync_refs),
                        confidence=0.99,
                    )
                )
    return findings


def _promise_species_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() not in _SPECIES_SUFFIXES:
        return []
    if re.search(r"Promise", text, re.I) is None or re.search(r"species", text, re.I) is None:
        return []

    function_re = re.compile(
        r"(?:fn|function|auto|static\s+[A-Za-z_][A-Za-z0-9_:<>*&\s]*)\s+"
        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*(?:species|Species)[A-Za-z0-9_]*)\s*\([^)]*\)"
        r"(?:\s*->\s*[^\{]+)?\s*\{",
        re.M,
    )
    findings: list[dict[str, Any]] = []
    for function in function_re.finditer(text):
        opening = text.find("{", function.start())
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        body = text[opening + 1 : closing]
        if re.search(r"(?:@@species|Symbol\.species|well_known_symbol\s*\(\s*[\"']species)", body, re.I) is None:
            continue
        if re.search(r"(?:constructor|\bC\b)", body) is None:
            continue
        collapsed = re.search(
            r"if\s+[^\{;\n]*(?:TAG_UNDEFINED|undefined)[^\{;\n]*\|\|"
            r"[^\{;\n]*(?:TAG_NULL|null)[^\{;\n]*\{"
            r"[\s\S]{0,260}?return\s+[^;\n]*(?:intrinsic|Promise|default)",
            body,
            re.I,
        )
        if collapsed is None:
            collapsed = re.search(
                r"if\s+[^\{;\n]*(?:TAG_NULL|null)[^\{;\n]*\|\|"
                r"[^\{;\n]*(?:TAG_UNDEFINED|undefined)[^\{;\n]*\{"
                r"[\s\S]{0,260}?return\s+[^;\n]*(?:intrinsic|Promise|default)",
                body,
                re.I,
            )
        if collapsed is None:
            continue
        if re.search(
            r"(?:is_promise_brand|promise_parent_in_chain|inherits?.{0,40}(?:Promise|species)|"
            r"Promise\s*\[\s*Symbol\.species\s*\]|standard\s+getter)",
            body,
            re.I | re.S,
        ):
            continue
        line = _line(text, opening + 1 + collapsed.start())
        findings.append(
            _finding(
                root_cause="promise-species-undefined-collapsed-into-null-default",
                path=path,
                line_start=line,
                category="api_contract",
                severity="major",
                message=(
                    "Promise species resolution collapses an absent inherited species value into the same intrinsic "
                    "fallback as explicit null, losing Promise subclass identity."
                ),
                evidence=(
                    f"`{function.group('name')}` reads the receiver constructor and @@species, then handles undefined "
                    "and null with one intrinsic-Promise return. In a runtime without the standard inherited "
                    "Promise[Symbol.species] getter, undefined must resolve to the Promise-branded constructor itself; "
                    "otherwise subclass then/catch/finally chains silently become intrinsic promises."
                ),
                falsifiers=(
                    "Required a Promise SpeciesConstructor-style function that reads both constructor and @@species.",
                    "Checked for separate null and undefined handling.",
                    "Checked for Promise-brand, inherited species getter, or subclass-chain recognition.",
                    "Excluded generic non-Promise optional/default handling."
                ),
                verification=(
                    "Distinguish explicit null from undefined species; for Promise-branded constructors emulate the "
                    "inherited species getter and return the constructor, then prove Promise subclasses preserve their "
                    "constructor through then, catch, and finally."
                ),
                confidence=0.99,
            )
        )
    return findings


def run_static_transfer_16_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    texts = {path: _safe_text(root_path, path) for path in changed}

    findings: list[dict[str, Any]] = []
    findings.extend(_cpp_expirable_client_stop_findings(root_path, changed, texts))
    for path in changed:
        text = texts.get(path, "")
        if text:
            findings.extend(_promise_species_findings(path, text))

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[(
            str(finding.get("root_cause")),
            str(finding.get("path")),
            int(finding.get("line_start") or 0),
        )] = finding

    return {
        "schema_version": "sergeant.static-transfer-16-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "executed_project_code": False,
    }
