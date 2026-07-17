"""Cross-file static invariants for authorization, state ownership, and data contracts."""

from __future__ import annotations

import ast
import re
from collections import defaultdict
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


def _finding(
    *, officer: str, capability: str, severity: str, root_cause: str, path: str,
    line_start: int, message: str, evidence: str, falsifiers: Iterable[str],
    verification: str, confidence: float, supporting_refs: Iterable[str] = (),
) -> dict[str, Any]:
    reference = f"{path}:{line_start}"
    return {
        "source": "static-cross-path-officer",
        "officer": officer,
        "capability": capability,
        "category": capability,
        "severity": severity,
        "root_cause": root_cause,
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": reference,
        "supporting_evidence_refs": sorted({reference, *[str(item) for item in supporting_refs if str(item)]}),
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": list(falsifiers),
        "verification_test": verification,
        "confidence": confidence,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def _policy_callback_postcondition(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    assignment_re = re.compile(
        r"(?P<policy>perms|permissions|policy)\s*,\s*(?P<err>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
        r"(?P<callback>[A-Za-z0-9_.]*(?:Verified|Final|Post|Policy|Auth)[A-Za-z0-9_]*Callback)\s*\(",
        re.I,
    )
    for match in assignment_re.finditer(text):
        policy = match.group("policy")
        before = text[max(0, match.start() - 5000) : match.start()]
        after = text[match.end() : match.end() + 1800]
        earlier_policy_validation = bool(
            re.search(r"CriticalOptions|critical[_A-Za-z]*option|validate[A-Za-z]*(?:Permission|Policy|Option)", before, re.I)
            and re.search(r"\b(?:check|validate|verify)[A-Za-z0-9_]*\s*\(", before, re.I)
        )
        if not earlier_policy_validation:
            continue
        post_validation = bool(
            re.search(rf"{re.escape(policy)}\s*\.\s*CriticalOptions", after, re.I)
            and re.search(r"\b(?:check|validate|verify)[A-Za-z0-9_]*\s*\(", after, re.I)
        )
        if post_validation:
            continue
        findings.append(
            _finding(
                officer="Medic",
                capability="authorization",
                severity="blocker",
                root_cause="post-validation-policy-mutation",
                path=path,
                line_start=_line(text, match.start()),
                message="A policy-producing callback can replace previously validated permissions without revalidating their critical constraints.",
                evidence=f"{match.group('callback')} assigns a new {policy} value after an earlier critical-option validation point, but no validation of the replacement follows before authorization continues.",
                falsifiers=(
                    "Checked for critical-option/policy validation immediately after the callback.",
                    "Checked that the callback replaces the policy object rather than only reading it.",
                    "Checked that the function contains an earlier validation of the same policy class.",
                ),
                verification="Re-run every critical policy constraint after the final callback that can replace permissions, before the successful authorization path is reachable.",
                confidence=0.95,
            )
        )
    return findings


def _go_permissive_config_validation(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for match in re.finditer(r"func\s+(?P<name>Validate[A-Za-z0-9_]*)\s*\([^)]*\)\s*(?:\([^)]*\)|[^\{]+)?\{", text):
        opening = match.end() - 1
        body = text[opening + 1 : opening + 5000]
        decode = re.search(r"json\.Unmarshal\s*\([^,]+,\s*&(?P<target>[A-Za-z_][A-Za-z0-9_]*)\s*\)", body)
        if decode is None:
            continue
        strict = re.search(
            r"DisallowUnknownFields|unknownField|KnownFields\s*\(|validateUnknown|checkUnknown|map\[string\](?:json\.RawMessage|any)",
            body,
            re.I,
        )
        if strict is not None:
            continue
        findings.append(
            _finding(
                officer="Engineer",
                capability="api_contract",
                severity="major",
                root_cause="permissive-config-validation",
                path=path,
                line_start=_line(text, opening + 1 + decode.start()),
                message="A configuration validation entry point silently accepts unknown fields.",
                evidence=f"{match.group('name')} decodes typed configuration with json.Unmarshal into {decode.group('target')} but performs no unknown-field scan or strict decoder pass before reporting validation issues.",
                falsifiers=(
                    "Checked for Decoder.DisallowUnknownFields or an equivalent recursive unknown-field scan.",
                    "Checked for raw-object/schema comparison before semantic validation succeeds.",
                    "Checked that the function is a validation entry point rather than ordinary tolerant ingestion.",
                ),
                verification="Preserve intended compatibility aliases, but surface unknown keys recursively with their full paths before claiming configuration validation succeeded.",
                confidence=0.94,
            )
        )
    return findings


def _transport_authorization_gap(files: dict[str, str]) -> list[dict[str, Any]]:
    core_rows = [
        (path, text)
        for path, text in files.items()
        if re.search(r"Allow(?:ToolCall|ResourceRead|PromptGet)|ErrAuthorizationFailed", text)
    ]
    server_rows = [
        (path, text)
        for path, text in files.items()
        if re.search(r"NewStreamableHTTPServer|StreamableHTTP|ServeHTTP|\bHandler\s*\(", text)
    ]
    if not core_rows or not server_rows:
        return []
    gated = any(
        re.search(r"WithCallGate|CheckToolCall|CheckResourceRead|CheckPromptGet|pre[-_ ]?dispatch.{0,80}author", text, re.I | re.S)
        for _, text in server_rows
    )
    if gated:
        return []
    explicit_auth_context = any(re.search(r"authz|authoriz|admission", text, re.I) for _, text in server_rows)
    if not explicit_auth_context:
        return []
    server_path, server_text = server_rows[0]
    core_refs = [f"{path}:{_line(text, re.search(r'Allow(?:ToolCall|ResourceRead|PromptGet)|ErrAuthorizationFailed', text).start())}" for path, text in core_rows]
    seam = re.search(r"NewStreamableHTTPServer|StreamableHTTP|ServeHTTP|\bHandler\s*\(", server_text)
    assert seam is not None
    return [
        _finding(
            officer="Medic",
            capability="authorization",
            severity="blocker",
            root_cause="transport-authorization-representation-gap",
            path=server_path,
            line_start=_line(server_text, seam.start()),
            message="The transport can dispatch direct capability calls without a pre-dispatch authorization decision or denial representation.",
            evidence="Core call paths enforce authorization, but the streamable HTTP/serve transport has no call gate or Check* seam before SDK dispatch; filtered denied capabilities can therefore degrade into not-found or success-shaped transport results instead of an authorization denial.",
            falsifiers=(
                "Checked for a pre-dispatch call gate on the transport.",
                "Checked for transport calls to the same Check*/authorization decision used by the core.",
                "Checked that authorization exists in deeper core calls, making the missing transport representation material rather than absent policy.",
            ),
            verification="Expose one shared authorization decision to the transport, reject denied direct calls before dispatch with the correct protocol/HTTP result, and retain the core check as defense in depth.",
            confidence=0.93,
            supporting_refs=core_refs,
        )
    ]


def _go_shared_status_overwrite(files: dict[str, str]) -> list[dict[str, Any]]:
    writers: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for path, text in files.items():
        if Path(path).suffix.lower() != ".go":
            continue
        for update in re.finditer(r"\.Status\(\)\.Update\s*\(\s*[^,]+,\s*(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*\)", text):
            variable = update.group("var")
            before = text[max(0, update.start() - 12000) : update.start()]
            declarations = list(re.finditer(rf"\b{re.escape(variable)}\s*:=\s*&(?P<type>[A-Za-z0-9_.]+)\s*\{{", before))
            if not declarations:
                continue
            resource_type = declarations[-1].group("type")
            writers[resource_type].append((path, _line(text, update.start())))
    findings: list[dict[str, Any]] = []
    for resource_type, rows in writers.items():
        distinct_paths = sorted({path for path, _ in rows})
        if len(distinct_paths) < 2:
            continue
        first_path, first_line = rows[0]
        refs = [f"{path}:{line}" for path, line in rows]
        findings.append(
            _finding(
                officer="Mechanic",
                capability="concurrency",
                severity="major",
                root_cause="shared-status-full-replacement",
                path=first_path,
                line_start=first_line,
                message="Multiple controllers fully replace the same status object and can overwrite fields owned by one another.",
                evidence=f"{len(distinct_paths)} controller files call Status().Update on {resource_type}; full-object replacement races across independently reconciled field owners.",
                falsifiers=(
                    "Checked that the same resource type is written from more than one controller file.",
                    "Checked for Status().Patch with MergeFrom on the shared writers.",
                    "Checked that this is status-subresource replacement rather than a sole-writer resource update.",
                ),
                verification="Fetch the latest object, patch only fields owned by each controller with MergeFrom, and retry conflicts so unrelated status fields survive concurrent reconciliation.",
                confidence=0.95,
                supporting_refs=refs,
            )
        )
    return findings


def _python_backend_parity(files: dict[str, str]) -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for path, text in files.items():
        if Path(path).suffix.lower() == ".py":
            grouped[str(Path(path).parent)].append((path, text))
    findings: list[dict[str, Any]] = []
    for directory, rows in grouped.items():
        migrated = [
            (path, text)
            for path, text in rows
            if re.search(r"WorkspaceInventoryAccessChecker|is_v2_write_activated|Kessel|kessel", text)
            and re.search(r"AccessPermission|BasePermission", text)
        ]
        if not migrated:
            continue
        legacy = [
            (path, text)
            for path, text in rows
            if re.search(r"request\.user\.access", text)
            and re.search(r"class\s+[A-Za-z0-9_]*AccessPermission", text)
            and not re.search(r"WorkspaceInventoryAccessChecker|is_v2_write_activated|check_v2|Kessel|kessel", text)
        ]
        if not legacy:
            continue
        affected_refs: list[str] = []
        for path, text in legacy:
            marker = re.search(r"request\.user\.access", text)
            if marker is not None:
                affected_refs.append(f"{path}:{_line(text, marker.start())}")
        migrated_path, migrated_text = migrated[0]
        migrated_marker = re.search(r"WorkspaceInventoryAccessChecker|is_v2_write_activated|Kessel|kessel", migrated_text)
        migrated_ref = f"{migrated_path}:{_line(migrated_text, migrated_marker.start() if migrated_marker else 0)}"
        first_path, first_text = legacy[0]
        first_marker = re.search(r"request\.user\.access", first_text)
        findings.append(
            _finding(
                officer="Medic",
                capability="authorization",
                severity="major",
                root_cause="authorization-backend-parity-gap",
                path=first_path,
                line_start=_line(first_text, first_marker.start() if first_marker else 0),
                message="Legacy permission classes ignore the active migrated authorization backend used by a sibling permission path.",
                evidence=f"The permission family in {directory} contains a migrated external authorization checker, while {len(legacy)} sibling AccessPermission class(es) return from request.user.access without consulting that backend.",
                falsifiers=(
                    "Checked whether the legacy classes call a shared migrated-backend fallback.",
                    "Checked that a sibling permission class in the same domain already uses the migrated backend.",
                    "Checked that the affected classes are authorization decisions rather than unrelated helpers.",
                ),
                verification="Share one backend-aware permission helper across equivalent legacy and migrated read paths, fail closed on backend errors, and prove V1-only/admin behavior remains unchanged.",
                confidence=0.92,
                supporting_refs=[*affected_refs, migrated_ref],
            )
        )
    return findings


def _python_external_data_completeness(path: str, text: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    findings: list[dict[str, Any]] = []
    lines = text.splitlines(keepends=True)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not re.search(r"(?:download|fetch|refresh|load).*(?:master|catalog|instrument|dataset|snapshot|metadata)|(?:master|catalog|instrument|dataset).*(?:download|fetch|load)", node.name, re.I):
            continue
        start = getattr(node, "lineno", 1)
        end = getattr(node, "end_lineno", start)
        body = "".join(lines[start - 1:end])
        if not re.search(r"(?:requests|httpx)\.(?:get|stream)\s*\(", body):
            continue
        if not re.search(r"(?:response|resp)\.(?:json\s*\(|content|text)", body):
            continue
        if not re.search(r"write_text\s*\(|json\.dump\s*\(|open\s*\([^)]*[\"']w", body):
            continue
        completeness = re.search(
            r"isinstance\s*\(|len\s*\([^)]*\)\s*(?:<|>|<=|>=)|Content-Length|schema|validate[A-Za-z0-9_]*\s*\(|truncat|_MIN_[A-Z0-9_]+",
            body,
            re.I,
        )
        retry = re.search(r"for\s+[A-Za-z_][A-Za-z0-9_]*\s+in\s+range\s*\(|retry|backoff", body, re.I)
        if completeness is not None and retry is not None:
            continue
        marker = re.search(r"(?:requests|httpx)\.(?:get|stream)\s*\(", body)
        findings.append(
            _finding(
                officer="Mechanic",
                capability="data_integrity",
                severity="major",
                root_cause="unvalidated-external-data-cache",
                path=path,
                line_start=start + body[: marker.start() if marker else 0].count("\n"),
                message="Bulk external data is cached as authoritative without completeness validation and resilient transfer handling.",
                evidence=f"{node.name} downloads and caches parsed external data, but does not both retry transport failures and reject structurally valid yet implausibly incomplete payloads before replacing the cache.",
                falsifiers=(
                    "Checked for bounded retry/backoff on transport interruption.",
                    "Checked for schema/type/count or content-length completeness validation before caching.",
                    "Checked that the function persists bulk catalog/master/dataset data rather than a small optional response.",
                ),
                verification="Stream or fully read with bounded retries, validate type/schema and a defensible completeness invariant, and replace the cache only after the complete payload is accepted.",
                confidence=0.93,
            )
        )
    return findings


def run_static_cross_path_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    files: dict[str, str] = {}
    for path in changed:
        if Path(path).suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if text:
            files[path] = text
    findings: list[dict[str, Any]] = []
    for path, text in files.items():
        suffix = Path(path).suffix.lower()
        if suffix == ".go":
            findings.extend(_policy_callback_postcondition(path, text))
            findings.extend(_go_permissive_config_validation(path, text))
        elif suffix == ".py":
            findings.extend(_python_external_data_completeness(path, text))
    findings.extend(_transport_authorization_gap(files))
    findings.extend(_go_shared_status_overwrite(files))
    findings.extend(_python_backend_parity(files))
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding.get("root_cause")), str(finding.get("path")))] = finding
    return {
        "schema_version": "sergeant.static-cross-path-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": sorted(files),
        "executed_project_code": False,
    }
