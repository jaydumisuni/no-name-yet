"""Static checks learned only after transfer set 18's blind 0/3 was frozen."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_TS_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}


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
        "source": "static-transfer-18-officer",
        "officer": "Mechanic" if category in {"lifecycle", "durability"} else "Engineer",
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


def _board_authority_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() not in _TS_SUFFIXES:
        return []
    if re.search(r"(?:private\s+)?_yaml\s*=|private\s+_yaml\b", text) is None:
        return []
    board = re.search(r"(?:_device|device)[^\n]{0,120}board_id|board_id[^\n]{0,120}(?:_device|device)", text)
    if board is None:
        return []
    install = re.search(r"(?:firmware|install)[A-Za-z0-9_$.]*\s*(?:\.|\()|_firmwareDialog", text, re.I)
    if install is None:
        return []
    consistency = re.search(
        r"readPlatformBoard|parseYaml[^\n]*(?:board|variant)|board(?:Mismatch|Disagree|Matches)|"
        r"yaml[^\n]{0,120}board_id|board_id[^\n]{0,120}yaml",
        text,
        re.I,
    )
    if consistency is not None:
        return []
    return [
        _finding(
            root_cause="install-path-trusts-stale-sidecar-without-yaml-authority-check",
            path=path,
            line_start=_line(text, install.start()),
            category="api_contract",
            severity="major",
            message="A save/install path trusts stored board metadata without proving it agrees with the live YAML source of truth.",
            evidence=(
                "The reviewed component owns editable YAML and separately resolves a stored device `board_id`, then exposes "
                "firmware/install actions without any visible board/variant consistency check or recovery route. A YAML board "
                "change can therefore leave the sidecar selection stale and repeatedly drive installation with the wrong target."
            ),
            falsifiers=(
                "Required both live YAML state and separately stored board identity in the same reviewed component.",
                "Required a save or install entry point that can consume the stored selection.",
                "Checked for YAML board parsing, explicit mismatch detection, install blocking or board-reselect recovery."
            ),
            verification=(
                "Compare the YAML board/variant against the stored board before save/install, block while they disagree, offer "
                "a compatible reselect path, and test YAML edits followed by every install entry point."
            ),
            supporting=(f"{path}:{_line(text, board.start())}",),
        )
    ]


def _required_secondary_persistence_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() not in _TS_SUFFIXES:
        return []
    set_item = re.search(r"setItem\s*:\s*\([^)]*\)[^{]*\{", text)
    if set_item is None:
        return []
    opening = text.find("{", set_item.start())
    closing = _matching_brace(text, opening)
    if closing is None:
        return []
    body = text[opening + 1 : closing]
    cookie = re.search(r"(?:write|set|sync)[A-Za-z0-9_]*Cookie\s*\(", body, re.I)
    if cookie is None:
        return []
    early = re.search(
        r"(?:localStorage|sessionStorage)\.setItem\s*\([^;]+;[\s\n]*return\s*;",
        body,
        re.I,
    )
    if early is None or early.start() > cookie.start():
        return []
    return [
        _finding(
            root_cause="successful-primary-persistence-skips-required-auth-cookie-sync",
            path=path,
            line_start=_line(text, opening + 1 + early.start()),
            category="durability",
            severity="blocker",
            message="A successful primary persistence path returns before the required authentication cookie is synchronized.",
            evidence=(
                "The storage adapter writes local/session storage and immediately returns on success, while cookie synchronization "
                "appears later in the same `setItem` contract. The cookie therefore runs only when earlier storage backends are "
                "unavailable or fail, leaving server-side/SSR authentication stale during normal operation."
            ),
            falsifiers=(
                "Required an explicit cookie synchronization sink later in the same persistence contract.",
                "Required an unconditional return after a successful primary storage write.",
                "Checked whether the cookie write occurs before the return or in a finally/shared epilogue."
            ),
            verification=(
                "Remove success-path returns, execute cookie synchronization from a shared epilogue, and prove local storage, "
                "session storage and cookie contain the same token state after every successful write."
            ),
            supporting=(f"{path}:{_line(text, opening + 1 + cookie.start())}",),
        )
    ]


def _persisted_field_mismatch_findings(texts: dict[str, str]) -> list[dict[str, Any]]:
    corpus = "\n".join(texts.values())
    if re.search(r"\brefreshToken\b", corpus) is None:
        return []
    findings: list[dict[str, Any]] = []
    for path, text in texts.items():
        if Path(path).suffix.lower() not in _TS_SUFFIXES:
            continue
        mismatch = re.search(r"state\?\s*:\s*\{[^}]*\brefresh\?\s*:|\.state\?\.refresh\b", text, re.S)
        if mismatch is None:
            continue
        if re.search(r"\.state\?\.refreshToken\b", text):
            continue
        findings.append(
            _finding(
                root_cause="persisted-auth-refresh-field-does-not-match-canonical-token-schema",
                path=path,
                line_start=_line(text, mismatch.start()),
                category="api_contract",
                severity="major",
                message="A security-sensitive consumer reads a persisted refresh field that does not exist in the canonical auth schema.",
                evidence=(
                    "The reviewed persistence contract defines `refreshToken`, but this consumer declares/reads `state.refresh`. "
                    "The value resolves empty, so account deletion/logout cannot send the actual refresh token for revocation."
                ),
                falsifiers=(
                    "Required canonical `refreshToken` evidence elsewhere in the reviewed source scope.",
                    "Required the consumer to read the distinct `refresh` field.",
                    "Checked whether the consumer also falls back to the canonical field."
                ),
                verification=(
                    "Use one shared persisted-auth reader/schema, pass the canonical refresh token to revocation, and test that "
                    "account deletion blacklists the exact stored token."
                ),
            )
        )
    return findings


def _thenable_body_validation_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() not in _TS_SUFFIXES:
        return []
    wrapper = re.search(r"function\s+(?P<name>wrap[A-Za-z0-9_]*Verb)\s*\([^)]*\)[^{]*\{", text)
    if wrapper is None:
        return []
    opening = text.find("{", wrapper.start())
    closing = _matching_brace(text, opening)
    if closing is None:
        return []
    body = text[opening + 1 : closing]
    direct = re.search(r"validateBody\s*\([^,]+,\s*rest\s*\[\s*0\s*\]", body)
    if direct is None:
        return []
    if re.search(r"\.then\s*\(|Promise\.resolve\s*\(|await\s+rest\s*\[\s*0\s*\]|typeof\s+[^\n]+\.then", body):
        return []
    return [
        _finding(
            root_cause="thenable-request-body-validated-before-resolution",
            path=path,
            line_start=_line(text, opening + 1 + direct.start()),
            category="api_contract",
            severity="major",
            message="Runtime request validation inspects a possibly thenable body before resolving it.",
            evidence=(
                f"`{wrapper.group('name')}` passes `rest[0]` directly to `validateBody` and immediately dispatches. The wrapper "
                "accepts an untyped HTTP body and contains no thenable/Promise resolution path, so streamed deserializers hand "
                "validation a Promise object and valid required fields appear missing."
            ),
            falsifiers=(
                "Required direct validation of the request-body slot in an HTTP verb wrapper.",
                "Checked for Promise.resolve, await, a `.then` branch or explicit thenable detection before validation.",
                "Did not flag ordinary synchronous programmatic calls without an HTTP wrapper."
            ),
            verification=(
                "Resolve thenable bodies before validation while preserving synchronous validation for plain values; test both "
                "valid and invalid promised bodies through the real streamed request path."
            ),
        )
    ]


def run_static_transfer_18_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    texts = {path: _safe_text(root_path, path) for path in changed}
    texts = {path: text for path, text in texts.items() if text}

    findings: list[dict[str, Any]] = []
    for path, text in texts.items():
        findings.extend(_board_authority_findings(path, text))
        findings.extend(_required_secondary_persistence_findings(path, text))
        findings.extend(_thenable_body_validation_findings(path, text))
    findings.extend(_persisted_field_mismatch_findings(texts))

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding.get("root_cause")), str(finding.get("path")), int(finding.get("line_start") or 0))] = finding

    return {
        "schema_version": "sergeant.static-transfer-18-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "executed_project_code": False,
    }
