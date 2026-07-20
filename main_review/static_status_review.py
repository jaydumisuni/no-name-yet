"""Static ownership analysis for shared status-subresource writers."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .static_async_epoch_review import run_static_async_epoch_review
from .static_async_lifecycle_review import run_static_async_lifecycle_review
from .static_async_publication_review import run_static_async_publication_review
from .static_authenticated_owner_review import run_static_authenticated_owner_review
from .static_auth_order_review import run_static_auth_order_review
from .static_await_state_review import run_static_await_state_review
from .static_component_async_review import run_static_component_async_review
from .static_contract_surface_review import run_static_contract_surface_review
from .static_core_contract_review import run_static_core_contract_review
from .static_dart_provider_lifetime_review import run_static_dart_provider_lifetime_review
from .static_external_integrity_review import run_static_external_integrity_review
from .static_js_auth_chrome_review import run_static_js_auth_chrome_review
from .static_js_auth_transition_review import run_static_js_auth_transition_review
from .static_js_controller_epoch_review import run_static_js_controller_epoch_review
from .static_js_remote_state_review import run_static_js_remote_state_review
from .static_preawait_durability_review import run_static_preawait_durability_review
from .static_python_cancellation_review import run_static_python_cancellation_review
from .static_recovery_review import run_static_recovery_review
from .static_remote_contract_review import run_static_remote_contract_review
from .static_selector_continuity_review import run_static_selector_continuity_review
from .static_stale_state_review import run_static_stale_state_review
from .static_terminal_state_review import run_static_terminal_state_review
from .static_transfer_10_replacement_review import (
    run_static_transfer_10_replacement_review,
)
from .static_transfer_11_review import run_static_transfer_11_review
from .static_transfer_12_review import run_static_transfer_12_review
from .static_transfer_13_review import run_static_transfer_13_review
from .static_transfer_14_review import run_static_transfer_14_review
from .static_transfer_15_review import run_static_transfer_15_review
from .static_transfer_16_review import run_static_transfer_16_review
from .static_transfer_17_review import run_static_transfer_17_review
from .static_transfer_18_review import run_static_transfer_18_review
from .static_transfer_19_review import run_static_transfer_19_review
from .static_transfer_20_review import run_static_transfer_20_review
from .static_transfer_9_review import run_static_transfer_9_review
from .static_transfer_review import run_static_transfer_review
from .static_url_path_contract_review import run_static_url_path_contract_review


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


def _infer_go_variable_type(text: str, variable: str, before_offset: int) -> str | None:
    before = text[:before_offset]
    candidates: list[tuple[int, str]] = []
    for match in re.finditer(
        rf"\b{re.escape(variable)}\s*(?::=|=)\s*&(?P<type>[A-Za-z_][A-Za-z0-9_.]*)\s*\{{",
        before,
    ):
        candidates.append((match.start(), match.group("type")))
    for match in re.finditer(
        rf"func\s*(?:\([^)]*\)\s*)?[A-Za-z_][A-Za-z0-9_]*\s*\((?P<params>[^)]*)\)",
        before,
        re.S,
    ):
        parameter = re.search(
            rf"(?:^|,)\s*{re.escape(variable)}\s+\*(?P<type>[A-Za-z_][A-Za-z0-9_.]*)\b",
            match.group("params"),
            re.S,
        )
        if parameter is not None:
            candidates.append((match.start(), parameter.group("type")))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _is_test_source(path: str) -> bool:
    candidate = Path(path)
    parts = {part.lower() for part in candidate.parts}
    name = candidate.name.lower()
    return (
        bool(parts & {"test", "tests", "testing", "fixtures"})
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith("_test.go")
        or name.endswith(".test.ts")
        or name.endswith(".test.tsx")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.tsx")
    )


def run_static_status_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    writers: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for path in changed:
        if Path(path).suffix.lower() != ".go":
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        for update in re.finditer(
            r"\.Status\(\)\.Update\s*\(\s*[^,]+,\s*(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*\)",
            text,
        ):
            variable = update.group("var")
            resource_type = _infer_go_variable_type(text, variable, update.start())
            if resource_type is not None:
                writers[resource_type].append((path, _line(text, update.start()), variable))

    findings: list[dict[str, Any]] = []
    for resource_type, rows in writers.items():
        distinct_paths = sorted({path for path, _, _ in rows})
        if len(distinct_paths) < 2:
            continue
        first_path, first_line, _ = rows[0]
        findings.append(
            {
                "source": "static-status-officer",
                "officer": "Mechanic",
                "capability": "concurrency",
                "category": "concurrency",
                "severity": "major",
                "root_cause": "shared-status-full-replacement",
                "path": first_path,
                "line_start": first_line,
                "line_end": first_line,
                "evidence_ref": f"{first_path}:{first_line}",
                "supporting_evidence_refs": sorted({f"{path}:{line}" for path, line, _ in rows}),
                "message": "Independent controllers fully replace the same status object and can overwrite fields owned by one another.",
                "evidence": f"{len(distinct_paths)} controller files call Status().Update on {resource_type}.",
                "falsifiers_checked": [
                    "Checked that the same resource type is written from more than one controller file.",
                    "Checked local allocations and typed function parameters for the updated object.",
                    "Checked that the relevant writes use Status().Update rather than field-scoped MergeFrom patches.",
                ],
                "verification_test": "Patch only fields owned by each controller and retry conflicts.",
                "confidence": 0.96,
                "direct_evidence": True,
                "admission_hint": "actionable",
            }
        )

    recovery = run_static_recovery_review(root_path, changed)
    stale_state = run_static_stale_state_review(root_path, changed)
    transfer = run_static_transfer_review(root_path, changed)
    core_contract = run_static_core_contract_review(root_path, changed)
    contract_surface = run_static_contract_surface_review(root_path, changed)
    remote_contract = run_static_remote_contract_review(root_path, changed)
    canonical_remote_paths = {
        str(item.get("path")) for item in remote_contract.get("findings", []) if isinstance(item, dict)
    }
    if canonical_remote_paths:
        contract_surface["findings"] = [
            item
            for item in contract_surface.get("findings", [])
            if not (
                str(item.get("root_cause")) == "malformed-collection-response-silently-treated-as-empty"
                and str(item.get("path")) in canonical_remote_paths
            )
        ]
        contract_surface["finding_count"] = len(contract_surface["findings"])
    async_lifecycle = run_static_async_lifecycle_review(root_path, changed)
    await_state = run_static_await_state_review(root_path, changed)
    js_remote_state = run_static_js_remote_state_review(root_path, changed)
    js_auth_chrome = run_static_js_auth_chrome_review(root_path, changed)
    js_auth_transition = run_static_js_auth_transition_review(root_path, changed)
    auth_order = run_static_auth_order_review(root_path, changed)
    authenticated_owner = run_static_authenticated_owner_review(root_path, changed)
    async_epoch = run_static_async_epoch_review(root_path, changed)
    js_controller_epoch = run_static_js_controller_epoch_review(root_path, changed)
    async_publication = run_static_async_publication_review(root_path, changed)
    dart_provider_lifetime = run_static_dart_provider_lifetime_review(root_path, changed)
    component_async = run_static_component_async_review(root_path, changed)
    python_cancellation = run_static_python_cancellation_review(root_path, changed)
    terminal_state = run_static_terminal_state_review(root_path, changed)
    external_integrity = run_static_external_integrity_review(root_path, changed)
    transfer_9 = run_static_transfer_9_review(root_path, changed)
    transfer_10_replacement = run_static_transfer_10_replacement_review(root_path, changed)
    transfer_11 = run_static_transfer_11_review(root_path, changed)
    transfer_12 = run_static_transfer_12_review(root_path, changed)
    transfer_13 = run_static_transfer_13_review(root_path, changed)
    transfer_14_changed = [path for path in changed if not _is_test_source(path)]
    transfer_14 = run_static_transfer_14_review(root_path, transfer_14_changed)
    transfer_15 = run_static_transfer_15_review(root_path, transfer_14_changed)
    transfer_16 = run_static_transfer_16_review(root_path, transfer_14_changed)
    transfer_17 = run_static_transfer_17_review(root_path, transfer_14_changed)
    transfer_18 = run_static_transfer_18_review(root_path, transfer_14_changed)
    transfer_19 = run_static_transfer_19_review(root_path, transfer_14_changed)
    transfer_20 = run_static_transfer_20_review(root_path, transfer_14_changed)
    selector_continuity = run_static_selector_continuity_review(root_path, changed)
    preawait_durability = run_static_preawait_durability_review(root_path, changed)
    url_path_contract = run_static_url_path_contract_review(root_path, changed)
    for result in (
        recovery,
        stale_state,
        transfer,
        core_contract,
        contract_surface,
        remote_contract,
        async_lifecycle,
        await_state,
        js_remote_state,
        js_auth_chrome,
        js_auth_transition,
        auth_order,
        authenticated_owner,
        async_epoch,
        js_controller_epoch,
        async_publication,
        dart_provider_lifetime,
        component_async,
        python_cancellation,
        terminal_state,
        external_integrity,
        transfer_9,
        transfer_10_replacement,
        transfer_11,
        transfer_12,
        transfer_13,
        transfer_14,
        transfer_15,
        transfer_16,
        transfer_17,
        transfer_18,
        transfer_19,
        transfer_20,
        selector_continuity,
        preawait_durability,
        url_path_contract,
    ):
        findings.extend(dict(item) for item in result.get("findings", []) if isinstance(item, dict))

    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding.get("root_cause")), str(finding.get("path")))] = finding

    return {
        "schema_version": "sergeant.static-status-review.v34",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "resource_writers": {
            resource_type: [
                {"path": path, "line": line, "variable": variable}
                for path, line, variable in rows
            ]
            for resource_type, rows in writers.items()
        },
        "static_recovery_review": recovery,
        "static_stale_state_review": stale_state,
        "static_transfer_review": transfer,
        "static_core_contract_review": core_contract,
        "static_contract_surface_review": contract_surface,
        "static_remote_contract_review": remote_contract,
        "static_async_lifecycle_review": async_lifecycle,
        "static_await_state_review": await_state,
        "static_js_remote_state_review": js_remote_state,
        "static_js_auth_chrome_review": js_auth_chrome,
        "static_js_auth_transition_review": js_auth_transition,
        "static_auth_order_review": auth_order,
        "static_authenticated_owner_review": authenticated_owner,
        "static_async_epoch_review": async_epoch,
        "static_js_controller_epoch_review": js_controller_epoch,
        "static_async_publication_review": async_publication,
        "static_dart_provider_lifetime_review": dart_provider_lifetime,
        "static_component_async_review": component_async,
        "static_python_cancellation_review": python_cancellation,
        "static_terminal_state_review": terminal_state,
        "static_external_integrity_review": external_integrity,
        "static_transfer_9_review": transfer_9,
        "static_transfer_10_replacement_review": transfer_10_replacement,
        "static_transfer_11_review": transfer_11,
        "static_transfer_12_review": transfer_12,
        "static_transfer_13_review": transfer_13,
        "static_transfer_14_review": transfer_14,
        "static_transfer_15_review": transfer_15,
        "static_transfer_16_review": transfer_16,
        "static_transfer_17_review": transfer_17,
        "static_transfer_18_review": transfer_18,
        "static_transfer_19_review": transfer_19,
        "static_transfer_20_review": transfer_20,
        "static_selector_continuity_review": selector_continuity,
        "static_preawait_durability_review": preawait_durability,
        "static_url_path_contract_review": url_path_contract,
        "executed_project_code": False,
    }
