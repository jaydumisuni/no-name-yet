"""Static ordering checks for authentication transitions and protected refetch."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}
_ENABLE_RE = re.compile(r"\b(?P<name>[A-Za-z_$][\w$]*(?:mfa|2fa|auth)[A-Za-z0-9_$]*(?:enable|activate|setup)|(?:enable|activate|setup)[A-Za-z0-9_$]*(?:mfa|2fa|auth)[A-Za-z0-9_$]*)\s*\(", re.I)
_READY_RE = re.compile(r"\b(?:mfaVerify|verifyMfa|verify2fa|refreshSession|setSessionToken|mintSession|exchangeSession|establishSession)\s*\(", re.I)
_INVALIDATE_RE = re.compile(r"\b(?:queryClient|qc)\.(?:invalidateQueries|refetchQueries|resetQueries|clear)\s*\(", re.I)
_HELPER_RE = re.compile(r"(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*\([^)]*\)\s*=>\s*\{", re.M)
_MUTATION_RE = re.compile(r"\buseMutation\s*\(\s*\{", re.M)


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


def _helpers(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for match in _HELPER_RE.finditer(text):
        opening = match.end() - 1
        closing = _matching_brace(text, opening)
        if closing is not None:
            result[match.group("name")] = text[opening + 1 : closing]
    return result


def _session_ready_call(text: str, helpers: dict[str, str]) -> bool:
    if _READY_RE.search(text):
        return True
    for call in re.finditer(r"\b([A-Za-z_$][\w$]*)\s*\(", text):
        body = helpers.get(call.group(1))
        if body is not None and _READY_RE.search(body):
            return True
    return False


def _finding(path: str, line: int) -> dict[str, Any]:
    return {
        "source": "static-auth-order-officer",
        "officer": "Mechanic",
        "capability": "state_lifecycle",
        "category": "state_lifecycle",
        "severity": "major",
        "root_cause": "protected-refetch-before-auth-session-ready",
        "path": path,
        "line_start": line,
        "line_end": line,
        "evidence_ref": f"{path}:{line}",
        "supporting_evidence_refs": [f"{path}:{line}"],
        "message": "Protected queries are invalidated before the authentication transition establishes its usable session.",
        "evidence": (
            "An MFA/auth enable mutation triggers protected-cache invalidation in its success path, then invokes a verify/session helper. "
            "The refetch can therefore run under the old authorization state and publish 401/403 or stale principal results."
        ),
        "falsifiers_checked": [
            "Checked that the mutation enables or activates an MFA/auth state rather than disabling or locking it.",
            "Checked that invalidate/refetch/reset/clear occurs before session verification or token establishment.",
            "Resolved local helper calls after invalidation to determine whether they perform verification/session setup.",
            "Checked whether enable and verification are already awaited in one mutation before invalidation/onSettled.",
        ],
        "verification_test": (
            "Make enable and session verification one ordered mutation, await the usable session first, then invalidate/refetch protected "
            "queries; prove the transition causes no authorization-error flood or auth-gate remount."
        ),
        "confidence": 0.97,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def run_static_auth_order_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    findings: list[dict[str, Any]] = []
    readable: list[str] = []

    for path in changed:
        if Path(path).suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        helpers = _helpers(text)
        for mutation in _MUTATION_RE.finditer(text):
            opening = mutation.end() - 1
            closing = _matching_brace(text, opening)
            if closing is None:
                continue
            body = text[opening + 1 : closing]
            enable = _ENABLE_RE.search(body)
            if enable is None:
                continue
            invalidate = _INVALIDATE_RE.search(body)
            if invalidate is None:
                continue
            before = body[: invalidate.start()]
            after = body[invalidate.end() :]
            # A fixed flow awaits session readiness in mutationFn before onSettled
            # invalidation. Any direct/helper readiness proof before invalidation is clean.
            if _session_ready_call(before, helpers):
                continue
            if not _session_ready_call(after, helpers):
                continue
            line = _line(text, opening + 1 + invalidate.start())
            findings.append(_finding(path, line))
            break

    unique = {(str(item["root_cause"]), str(item["path"])): item for item in findings}
    return {
        "schema_version": "sergeant.static-auth-order-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
