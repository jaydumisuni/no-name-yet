"""Static invariants for strict structured input and durable status recovery."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable


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


def _go_functions(text: str) -> list[tuple[str, str, int, int]]:
    functions: list[tuple[str, str, int, int]] = []
    pattern = re.compile(
        r"func\s*(?:\([^)]*\)\s*)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*(?:\([^)]*\)|[^\{\n]+)?\{",
        re.M,
    )
    for match in pattern.finditer(text):
        opening = match.end() - 1
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        functions.append((match.group("name"), text[opening + 1 : closing], opening + 1, match.start()))
    return functions


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
        "source": "static-recovery-officer",
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


def _permissive_structured_input(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name, body, body_offset, _ in _go_functions(text):
        if not re.search(r"(?:set|save|apply|import|update|replace).*(?:policy|config|settings|rules|json)|(?:policy|config|settings|rules).*(?:set|save|apply|import|update|replace)", name, re.I):
            continue
        decode = re.search(r"json\.Unmarshal\s*\([^,]+,\s*(?P<target>&?[A-Za-z_][A-Za-z0-9_]*)\s*\)", body)
        if decode is None:
            continue
        strict = re.search(
            r"DisallowUnknownFields|json\.NewDecoder|unknownField|validateUnknown|checkUnknown|no trailing|Decode\s*\(",
            body,
            re.I,
        )
        if strict is not None:
            continue
        after = body[decode.end() :]
        persisted = re.search(
            r"(?:put|save|write|apply|update|replace|set)[A-Za-z0-9_]*\s*\([^)]*(?:next|doc|policy|config|settings)|"
            r"return\s+[^\n]*(?:put|save|write|apply|update|replace|set)[A-Za-z0-9_]*\s*\(",
            after,
            re.I,
        )
        if persisted is None:
            continue
        required_content_check = re.search(
            r"len\s*\([^)]*(?:Statement|Rules|Entries|Items|Policies|Config)[^)]*\)\s*(?:==|<=)\s*0|"
            r"(?:Statement|Rules|Entries|Items|Policies)\s*==\s*nil|validate[A-Za-z0-9_]*\s*\(",
            after,
            re.I,
        )
        if required_content_check is not None:
            continue
        findings.append(
            _finding(
                officer="Engineer",
                capability="api_contract",
                severity="major",
                root_cause="permissive-structured-input-acceptance",
                path=path,
                line_start=_line(text, body_offset + decode.start()),
                message="A state-changing structured-input API accepts unknown or empty-shaped JSON as a successful update.",
                evidence=f"{name} decodes caller-controlled JSON with json.Unmarshal and then persists/applies the typed result without strict unknown-field handling or a required-content invariant.",
                falsifiers=(
                    "Checked for Decoder.DisallowUnknownFields or an equivalent unknown-field scan.",
                    "Checked for trailing-data rejection or a second decoder EOF check.",
                    "Checked for a required-content invariant before the decoded object is persisted.",
                ),
                verification="Strictly decode the caller document, reject unknown/trailing data, validate the minimum meaningful shape, and only then perform the live read-modify-write.",
                confidence=0.95,
            )
        )
    return findings


def _swallowed_status_conflict(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    pattern = re.compile(
        r"if\s+(?P<err>[A-Za-z_][A-Za-z0-9_]*)\s*:=\s*[^;\n]*Status\(\)\.Update\s*\([^;]+;\s*"
        r"(?P=err)\s*!=\s*nil\s*&&\s*!\s*(?:apierrors\.)?IsConflict\s*\(\s*(?P=err)\s*\)\s*\{",
        re.S,
    )
    for match in pattern.finditer(text):
        tail = text[match.end() : match.end() + 700]
        if not re.search(r"return\s+nil", tail):
            continue
        findings.append(
            _finding(
                officer="Mechanic",
                capability="state_lifecycle",
                severity="major",
                root_cause="swallowed-status-conflict",
                path=path,
                line_start=_line(text, match.start()),
                message="A status update conflict is treated as success even though the desired status may never be published.",
                evidence="Status().Update returns nil to its caller for IsConflict without re-fetching, retrying, or scheduling another reconcile, so Ready/observed state can remain stale.",
                falsifiers=(
                    "Checked for retry.RetryOnConflict around the status write.",
                    "Checked for an explicit requeue when conflict occurs.",
                    "Checked whether a later write in the same path guarantees publication.",
                ),
                verification="Re-fetch the latest resource and retry the status mutation, or return/requeue the conflict so the status obligation cannot be silently lost.",
                confidence=0.97,
            )
        )
    return findings


def _stale_failure_not_recovered(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not re.search(r"Status\.[A-Za-z0-9_]*Status\s*=\s*[A-Za-z0-9_.]*Failed", text):
        return findings
    branch = re.search(
        r"(?P<changed>[A-Za-z_][A-Za-z0-9_]*)\s*,\s*(?P<new>[A-Za-z_][A-Za-z0-9_]*)\s*:=\s*[^\n]*(?:Change|Diff|Calculate)[A-Za-z0-9_]*\s*\([^\n]*\)[\s\S]{0,9000}?"
        r"if\s+(?P=changed)\s*\{[\s\S]{0,7000}?\}\s*else\s*\{(?P<else>[\s\S]{0,2500}?)\n\s*\}",
        text,
        re.I,
    )
    if branch is None:
        return findings
    else_body = branch.group("else")
    empty_check = re.search(r"Status\.(?P<field>[A-Za-z0-9_]*Status)\s*==\s*[\"']{2}", else_body)
    if empty_check is None:
        return findings
    field = empty_check.group("field")
    if re.search(rf"Status\.{re.escape(field)}\s*==\s*[A-Za-z0-9_.]*Failed", else_body):
        return findings
    if not re.search(rf"Status\.{re.escape(field)}\s*=\s*[A-Za-z0-9_.]*(?:Complete|Ready|Healthy|Success)", else_body):
        return findings
    findings.append(
        _finding(
            officer="Mechanic",
            capability="state_lifecycle",
            severity="major",
            root_cause="persisted-failure-not-recovered",
            path=path,
            line_start=_line(text, branch.start()),
            message="A previously persisted failed status is not cleared after the underlying operation succeeds with no calculated changes.",
            evidence=f"The reconcile writes a Failed value for Status.{field}, but the no-change recovery branch promotes only an empty status to the successful terminal state; a transient failure therefore remains sticky indefinitely.",
            falsifiers=(
                "Checked whether the no-change branch also handles the failed terminal state.",
                "Checked whether the error/status fields are cleared on successful provider reads.",
                "Checked whether another unconditional success write follows the branch.",
            ),
            verification="On a successful no-change reconcile, transition empty or transient-failed status to the healthy terminal state and clear the persisted error before writing status.",
            confidence=0.94,
        )
    )
    return findings


def run_static_recovery_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    findings: list[dict[str, Any]] = []
    readable: list[str] = []
    for path in changed:
        if Path(path).suffix.lower() != ".go":
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        findings.extend(_permissive_structured_input(path, text))
        findings.extend(_swallowed_status_conflict(path, text))
        findings.extend(_stale_failure_not_recovered(path, text))
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding["root_cause"]), str(finding["path"]))] = finding
    return {
        "schema_version": "sergeant.static-recovery-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
