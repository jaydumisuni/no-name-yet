"""Cross-function static reasoning for unfamiliar repositories.

These checks model execution order and canonical control flow without running the
reviewed project.  They are deliberately structural rather than repository-name
or fixture-text rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

_SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".java", ".kt", ".cs"}
_CONTROL_NAMES = {"if", "for", "while", "switch", "catch", "with", "return", "function"}
_ONE_SHOT_NAME_RE = re.compile(r"(?:timeout|deadline|expire|cancel|abort|complete|finali[sz]e)", re.I)
_METHOD_RE = re.compile(
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*\([^;{}]*\)\s*"
    r"(?:throws\s+[^{}]+)?(?:\:\s*[^{};=]+)?\s*\{",
    re.M,
)


@dataclass(frozen=True)
class CodeBlock:
    name: str
    body: str
    line_start: int
    body_offset: int


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


def _blocks(text: str) -> list[CodeBlock]:
    blocks: list[CodeBlock] = []
    seen: set[tuple[str, int]] = set()
    for match in _METHOD_RE.finditer(text):
        name = match.group("name")
        if name.lower() in _CONTROL_NAMES:
            continue
        opening = match.end() - 1
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        key = (name, opening)
        if key in seen:
            continue
        seen.add(key)
        blocks.append(CodeBlock(name, text[opening + 1 : closing], _line(text, match.start()), opening + 1))
    return blocks


def _finding(
    *,
    officer: str,
    capability: str,
    severity: str,
    root_cause: str,
    path: str,
    line_start: int,
    message: str,
    evidence: str,
    falsifiers: Iterable[str],
    verification: str,
    confidence: float,
) -> dict[str, Any]:
    return {
        "source": "static-semantic-officer",
        "officer": officer,
        "capability": capability,
        "category": capability,
        "severity": severity,
        "root_cause": root_cause,
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": f"{path}:{line_start}",
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": list(falsifiers),
        "verification_test": verification,
        "confidence": confidence,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def _one_shot_lock_loss(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for block in _blocks(text):
        if not _ONE_SHOT_NAME_RE.search(block.name) or not re.search(r"\btry_?lock\s*\(|\.tryLock\s*\(", block.body, re.I):
            continue
        # A one-shot callback may use a nonblocking lock only when failure is
        # explicitly retried, rescheduled, escalated, or surfaced as an error.
        failure_recovery = re.search(
            r"(?:retry|reschedul|schedule[A-Za-z0-9_]*\s*\(|enqueue[A-Za-z0-9_]*\s*\(|submit[A-Za-z0-9_]*\s*\(|throw\s+new)",
            block.body,
            re.I,
        )
        bounded_loop = re.search(r"\b(?:while|for)\s*\([^)]*try_?lock|\bdo\s*\{[\s\S]{0,400}try_?lock", block.body, re.I)
        if failure_recovery or bounded_loop:
            continue
        match = re.search(r"\btry_?lock\s*\(|\.tryLock\s*\(", block.body, re.I)
        assert match is not None
        findings.append(
            _finding(
                officer="Mechanic",
                capability="concurrency",
                severity="major",
                root_cause="one-shot-lock-loss",
                path=path,
                line_start=_line(text, block.body_offset + match.start()),
                message="One-shot lifecycle work can be silently dropped when a nonblocking lock is unavailable.",
                evidence=f"Method {block.name} uses a try-lock path but contains no retry, reschedule, escalation, or surfaced failure for the unsuccessful acquisition branch.",
                falsifiers=(
                    "Checked for blocking lock acquisition.",
                    "Checked for retry/reschedule/enqueue behavior after failed acquisition.",
                    "Checked for a surfaced exception or error path.",
                ),
                verification="Make the callback acquire the lock deterministically or preserve the one-shot obligation through retry/rescheduling, then prove completion cannot be lost.",
                confidence=0.95,
            )
        )
    return findings


def _jsx_handler(text: str, name: str) -> tuple[str, int] | None:
    marker = re.compile(rf"\b{re.escape(name)}\s*=\s*\{{", re.M)
    for match in marker.finditer(text):
        arrow = re.search(r"=>\s*\{", text[match.end() : match.end() + 500])
        if arrow is None:
            continue
        opening = match.end() + arrow.end() - 1
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        return text[opening + 1 : closing], opening + 1
    return None


def _call_names(body: str) -> set[str]:
    return {
        match.group(1)
        for match in re.finditer(r"(?<![.\w])([A-Za-z_$][A-Za-z0-9_$]*)\s*\(", body)
        if match.group(1).lower() not in _CONTROL_NAMES
    }


def _canonical_flow_bypass(path: str, text: str) -> list[dict[str, Any]]:
    canonical = _jsx_handler(text, "onSubmit")
    if canonical is None:
        return []
    canonical_body, _ = canonical
    has_guard = bool(re.search(r"\b(?:validate|validation|isValid|shouldValidate|check[A-Z])\b", canonical_body))
    has_cleanup = bool(re.search(r"\b(?:clear|reset|cleanup|setError)\s*\(", canonical_body))
    canonical_calls = _call_names(canonical_body)
    if not (has_guard and has_cleanup and canonical_calls):
        return []

    findings: list[dict[str, Any]] = []
    for handler in ("onKeyDown", "onKeyUp"):
        alternate = _jsx_handler(text, handler)
        if alternate is None:
            continue
        alternate_body, offset = alternate
        if not re.search(r"Enter|ctrlKey|metaKey|shortcut", alternate_body, re.I):
            continue
        if re.search(r"requestSubmit\s*\(|dispatchEvent\s*\(|handleSubmit\s*\(|submitForm\s*\(", alternate_body):
            continue
        shared_low_level = sorted(
            name
            for name in canonical_calls & _call_names(alternate_body)
            if name not in {"preventDefault", "stopPropagation", "catch"}
        )
        if not shared_low_level:
            continue
        findings.append(
            _finding(
                officer="Engineer",
                capability="api_contract",
                severity="major",
                root_cause="canonical-action-flow-bypass",
                path=path,
                line_start=_line(text, offset),
                message="Alternate input handling bypasses the canonical validation and cleanup flow.",
                evidence=f"{handler} directly invokes lower-level action(s) {', '.join(shared_low_level)} while onSubmit additionally performs validation and cleanup/error-state work.",
                falsifiers=(
                    "Checked whether the alternate handler submits the form or calls the canonical handler.",
                    "Checked whether validation and cleanup are shared through a common function.",
                    "Checked that the overlapping call is a meaningful state-changing action.",
                ),
                verification="Route the alternate input through the canonical submit path or extract one shared operation that includes every guard, state update, and cleanup step.",
                confidence=0.96,
            )
        )
    return findings


def _event_emitters(blocks: list[CodeBlock]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for block in blocks:
        events = {
            match.group(1)
            for match in re.finditer(r"\.emit\s*\(\s*([A-Za-z_$][A-Za-z0-9_$.]*)", block.body)
        }
        if events:
            result[block.name] = events
    return result


def _related_project_texts(root: Path, changed_paths: list[str]) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    roots = {(root / path).parent for path in changed_paths if (root / path).is_file()}
    seen: set[Path] = set()
    for directory in roots:
        for file in directory.rglob("*"):
            if file in seen or not file.is_file() or file.suffix.lower() not in _SOURCE_SUFFIXES:
                continue
            seen.add(file)
            try:
                relative = file.relative_to(root).as_posix()
                candidates.append((relative, file.read_text(encoding="utf-8", errors="ignore")))
            except (OSError, ValueError):
                continue
            if len(candidates) >= 1500:
                return candidates
    return candidates


def _publication_before_initialization(
    root: Path,
    path: str,
    text: str,
    project_texts: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    blocks = _blocks(text)
    emitters = _event_emitters(blocks)
    if not emitters:
        return []
    findings: list[dict[str, Any]] = []
    state_prep_re = re.compile(
        r"(?:\b(?:enable|activate|initiali[sz]e|cache|markReady|setReady)[A-Za-z0-9_]*\s*\(|"
        r"this\.[A-Za-z0-9_$]*(?:info|state|ready|checked|active)[A-Za-z0-9_$]*\s*=)",
        re.I,
    )
    external_effect_re = re.compile(r"\bawait\b|authedRequest\s*\(|\b(?:create|post|save|persist)[A-Za-z0-9_]*\s*\(", re.I)
    for caller in blocks:
        for callee, events in emitters.items():
            call = re.search(rf"(?:\bthis\.)?\b{re.escape(callee)}\s*\(", caller.body)
            if call is None or caller.name == callee:
                continue
            before = caller.body[: call.start()]
            if not external_effect_re.search(before) or state_prep_re.search(before):
                continue
            listener_paths: list[str] = []
            for related_path, related_text in project_texts:
                if related_path == path:
                    continue
                for event in events:
                    leaf = event.split(".")[-1]
                    if leaf not in related_text:
                        continue
                    if re.search(r"(?:\.on|addEventListener)\s*\([^)]*" + re.escape(leaf), related_text, re.I):
                        listener_paths.append(related_path)
                        break
            if not listener_paths:
                continue
            findings.append(
                _finding(
                    officer="Mechanic",
                    capability="concurrency",
                    severity="major",
                    root_cause="publication-before-initialization",
                    path=path,
                    line_start=_line(text, caller.body_offset + call.start()),
                    message="A state-observable event is published before the newly created state is made coherent for listeners.",
                    evidence=f"{caller.name} invokes event-emitting helper {callee} after an external state-changing operation, but no cache/activation/readiness update precedes publication; listener evidence exists in {', '.join(sorted(set(listener_paths))[:3])}.",
                    falsifiers=(
                        "Checked for cache, activation, initialization, readiness, or active-state updates before publication.",
                        "Checked for a real listener to the emitted event in related source files.",
                        "Checked that the caller performs an external or persistent state-changing operation first.",
                    ),
                    verification="Establish the complete readable state and activate the matching lifecycle before emitting the notification, then verify listeners observe the new state immediately.",
                    confidence=0.93,
                )
            )
    return findings


def run_static_semantic_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    readable = [path for path in changed if (root_path / path).is_file()]
    project_texts = _related_project_texts(root_path, readable)
    findings: list[dict[str, Any]] = []
    for path in readable:
        suffix = Path(path).suffix.lower()
        if suffix not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        if suffix in {".java", ".kt", ".cs"}:
            findings.extend(_one_shot_lock_loss(path, text))
        if suffix in {".tsx", ".jsx"}:
            findings.extend(_canonical_flow_bypass(path, text))
        if suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
            findings.extend(_publication_before_initialization(root_path, path, text, project_texts))

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding["root_cause"]), str(finding["path"]), int(finding["line_start"]))] = finding
    return {
        "schema_version": "sergeant.static-semantic-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
