"""Transfer-grade static invariants learned from independent repository defects.

These checks remain deterministic and repository-grounded.  They do not execute
project code and they deliberately require a complete contract shape rather than
promoting broad lexical co-presence into an actionable finding.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Iterable


_SOURCE_SUFFIXES = {".go", ".py"}


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


def _go_functions(text: str) -> list[tuple[str, str, int]]:
    functions: list[tuple[str, str, int]] = []
    pattern = re.compile(
        r"func\s*(?:\([^)]*\)\s*)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*"
        r"(?:\([^)]*\)|[^\{\n]+)?\{",
        re.M,
    )
    for match in pattern.finditer(text):
        opening = match.end() - 1
        closing = _matching_brace(text, opening)
        if closing is not None:
            functions.append((match.group("name"), text[opening + 1 : closing], opening + 1))
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
    supporting_refs: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "source": "static-transfer-officer",
        "officer": officer,
        "capability": capability,
        "category": capability,
        "severity": severity,
        "root_cause": root_cause,
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": f"{path}:{line_start}",
        "supporting_evidence_refs": list(supporting_refs),
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": list(falsifiers),
        "verification_test": verification,
        "confidence": confidence,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def _go_transient_notfound_status_loss(path: str, text: str) -> list[dict[str, Any]]:
    """Find one-shot status work that treats a cache NotFound as success.

    A NotFound returned from a controller-runtime cache can be transient just
    after object creation.  Returning nil from inside the retry closure consumes
    the report and prevents both retry and later delivery of the status.
    """

    if not re.search(r"\.Dequeue\s*\(\s*ctx\s*\)", text):
        return []
    if not re.search(r"sync[A-Za-z0-9_]*Status\s*\(", text):
        return []

    findings: list[dict[str, Any]] = []
    for function_name, body, body_offset in _go_functions(text):
        if "status" not in function_name.lower():
            continue
        if not re.search(r"retry\.(?:Do|OnError|RetryOnConflict)|utilretry\.RetryOnConflict", body):
            continue
        if not re.search(r"Status\(\)\.(?:Update|Patch)|Patch[A-Za-z0-9_]*Status|Build[A-Za-z0-9_]*Status", body):
            continue

        for branch in re.finditer(
            r"if\s+(?:apierrors\.)?IsNotFound\s*\(\s*(?P<err>[A-Za-z_][A-Za-z0-9_]*)\s*\)\s*\{",
            body,
        ):
            opening = branch.end() - 1
            closing = _matching_brace(body, opening)
            if closing is None:
                continue
            branch_body = body[opening + 1 : closing]
            returns_success = bool(re.search(r"\breturn\s+(?:nil|ctrl\.Result\{\}\s*,\s*nil)\b", branch_body))
            preserves_retry = bool(
                re.search(
                    rf"\breturn\s+{re.escape(branch.group('err'))}\b|Requeue|retry\.|RetryOnConflict",
                    branch_body,
                )
            )
            if not returns_success or preserves_retry:
                continue
            line_start = _line(text, body_offset + branch.start())
            findings.append(
                _finding(
                    officer="Mechanic",
                    capability="state_lifecycle",
                    severity="major",
                    root_cause="transient-cache-notfound-drops-status",
                    path=path,
                    line_start=line_start,
                    message="A transient cache NotFound is accepted as successful completion of a one-shot status report.",
                    evidence=(
                        f"{function_name} runs beneath a dequeued status-report path and a retry wrapper, but its "
                        "IsNotFound branch returns nil. The retry therefore stops and the consumed report has no "
                        "remaining trigger to publish the required status when the cache becomes current."
                    ),
                    falsifiers=(
                        "Checked that status work is fed by a dequeued report rather than a level-triggered reconcile.",
                        "Checked that the NotFound branch returns success from inside retry-controlled status work.",
                        "Checked for an error return, explicit retry, requeue, or direct API-reader fallback in the branch.",
                    ),
                    verification=(
                        "Retry cache NotFound for the bounded status-write window (or read from an authoritative client), "
                        "then prove a report arriving before cache visibility still publishes status exactly once."
                    ),
                    confidence=0.97,
                )
            )
            break
    return findings


def _go_scoped_credential_gap(files: dict[str, str]) -> list[dict[str, Any]]:
    scoped_refs: list[str] = []
    validator_refs: list[str] = []
    for path, text in files.items():
        if Path(path).suffix.lower() != ".go":
            continue
        permission = re.search(r"Permissions\s+\[\][A-Za-z0-9_.]+|Permissions\s*:\s*[A-Za-z0-9_.]+", text)
        create_with_scope = re.search(r"Create[A-Za-z0-9_]*APIKey[\s\S]{0,500}Permissions", text)
        validator = re.search(r"ValidateUserAPIKey(?:API)?\s*\(", text)
        if permission and create_with_scope:
            scoped_refs.append(f"{path}:{_line(text, permission.start())}")
        if validator:
            validator_refs.append(f"{path}:{_line(text, validator.start())}")

    if not scoped_refs or not validator_refs:
        return []

    findings: list[dict[str, Any]] = []
    for path, text in files.items():
        if Path(path).suffix.lower() != ".go":
            continue
        for function_name, body, body_offset in _go_functions(text):
            if not re.search(r"require.*Permission|authorize|check.*Permission", function_name, re.I):
                continue
            admin_key = re.search(r"checkAdminAPIKey\s*\(", body)
            bearer = re.search(r"extractBearerToken\s*\(|Bearer", body)
            token_required = re.search(r"if\s+[A-Za-z_][A-Za-z0-9_]*\s*==\s*[\"']{2}[\s\S]{0,300}?401", body)
            if not (admin_key and bearer and token_required):
                continue
            user_key_authorized = re.search(
                r"HasAPIKeyPermission|ValidateUserAPIKey|ComputeEffectivePermissions|AuthorizeUserAPIKey|CheckAPIKeyScope",
                body,
            )
            if user_key_authorized:
                continue
            line_start = _line(text, body_offset + admin_key.start())
            findings.append(
                _finding(
                    officer="Medic",
                    capability="authorization",
                    severity="major",
                    root_cause="credential-scope-not-enforced",
                    path=path,
                    line_start=line_start,
                    message="A scoped user credential is persisted and validatable but never enters the central permission decision.",
                    evidence=(
                        f"{function_name} recognizes only the infrastructure/admin API key before requiring a bearer "
                        "session. The repository separately stores per-key permissions and exposes user-key validation, "
                        "but this request gate calls neither path, so the scoped credential cannot be authorized according "
                        "to its own limits."
                    ),
                    falsifiers=(
                        "Checked that per-key permission data is persisted during credential creation.",
                        "Checked that a user-key validation path exists independently of the admin key.",
                        "Checked the complete central permission function for user-key validation and effective-scope enforcement.",
                    ),
                    verification=(
                        "Validate the user API key at the permission gate, intersect its scope with owner authority, fail "
                        "closed on lookup errors, and prove in-scope, out-of-scope, invalid-key and bearer-fallback cases."
                    ),
                    confidence=0.98,
                    supporting_refs=[*scoped_refs, *validator_refs],
                )
            )
            break
    return findings


def _python_function_segments(text: str) -> list[tuple[str, str, int]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    lines = text.splitlines(keepends=True)
    segments: list[tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = getattr(node, "lineno", 1)
        end = getattr(node, "end_lineno", start)
        segments.append((node.name, "".join(lines[start - 1 : end]), start))
    return segments


def _python_destructive_rebuild(path: str, text: str) -> list[dict[str, Any]]:
    helpers: list[tuple[str, str, int, str]] = []
    for function_name, body, start_line in _python_function_segments(text):
        if not re.search(r"(?:database|index|store|cache|artifact|build|initial)", function_name, re.I):
            continue
        pattern = re.search(
            r"if\s+(?P<var>[A-Za-z_][A-Za-z0-9_.]*)\.exists\s*\(\s*\)\s*:\s*\n"
            r"\s*(?P=var)\.unlink\s*\(\s*\)[\s\S]{0,500}?sqlite3\.connect\s*\(\s*(?P=var)\s*\)",
            body,
        )
        if pattern is None:
            continue
        if re.search(r"tempfile|NamedTemporaryFile|\.tmp\b|with_suffix\s*\(|os\.replace\s*\(|\.replace\s*\(", body):
            continue
        helpers.append((function_name, body, start_line, pattern.group("var")))

    if not helpers:
        return []

    findings: list[dict[str, Any]] = []
    for helper_name, helper_body, helper_line, variable in helpers:
        call = re.search(
            rf"{re.escape(helper_name)}\s*\(\s*(?P<target>[^\n\)]+(?:knowledge_db|db_path|index_path|database)[^\n\)]*)\s*\)",
            text,
            re.I,
        )
        if call is None and not re.search(r"rebuild|build.*index", helper_name, re.I):
            continue
        helper_offset = text.find(helper_body)
        unlink = re.search(rf"{re.escape(variable)}\.unlink\s*\(", helper_body)
        line_start = helper_line if unlink is None else _line(text, helper_offset + unlink.start())
        supporting = []
        if call is not None:
            supporting.append(f"{path}:{_line(text, call.start())}")
        findings.append(
            _finding(
                officer="Medic",
                capability="state_lifecycle",
                severity="major",
                root_cause="destructive-in-place-rebuild",
                path=path,
                line_start=line_start,
                message="A rebuild deletes the authoritative database before a replacement has completed successfully.",
                evidence=(
                    f"{helper_name} unlinks {variable} and reconnects SQLite at the same authoritative path. A later parse, "
                    "insert, or commit failure therefore destroys the last valid index instead of preserving it until a "
                    "fully built replacement is ready."
                ),
                falsifiers=(
                    "Checked for a temporary database path distinct from the authoritative target.",
                    "Checked for atomic os.replace/Path.replace publication after a successful build.",
                    "Checked that the helper is used by an index/database rebuild path rather than disposable test setup.",
                ),
                verification=(
                    "Build and validate a temporary database in the same filesystem, close it successfully, atomically "
                    "replace the authoritative path, clean WAL/SHM/temp sidecars, and prove failure preserves the old DB."
                ),
                confidence=0.98,
                supporting_refs=supporting,
            )
        )
    return findings


def run_static_transfer_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    files: dict[str, str] = {}
    findings: list[dict[str, Any]] = []
    for path in changed:
        if Path(path).suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        files[path] = text
        if Path(path).suffix.lower() == ".go":
            findings.extend(_go_transient_notfound_status_loss(path, text))
        elif Path(path).suffix.lower() == ".py":
            findings.extend(_python_destructive_rebuild(path, text))

    findings.extend(_go_scoped_credential_gap(files))
    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding["root_cause"]), str(finding["path"]), int(finding["line_start"]))] = finding
    return {
        "schema_version": "sergeant.static-transfer-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": sorted(files),
        "executed_project_code": False,
    }
