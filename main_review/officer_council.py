"""Canonical deterministic permanent-officer review formation.

Models can add bounded evidence to these packets, but the formation exists and
adjudicates repository evidence even when every model route is unavailable.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .cpl_campaign import build_cpl_campaign
from .offline_investigation import run_offline_investigations


OFFICER_ORDER = (
    "Quartermaster",
    "Scout",
    "Engineer",
    "Medic",
    "Mechanic",
    "Analyst",
    "Challenger",
    "Archivist",
    "Judge",
    "Hermes",
)
OFFICER_BY_CAPABILITY = {
    "architecture": "Engineer",
    "api_contract": "Engineer",
    "call_graph": "Engineer",
    "cross_file": "Engineer",
    "regression": "Engineer",
    "test_impact": "Engineer",
    "testing": "Engineer",
    "security": "Medic",
    "security_taint": "Medic",
    "data_flow": "Medic",
    "risk": "Scout",
    "performance": "Mechanic",
    "concurrency": "Mechanic",
}
_GENERIC_RISK_MESSAGES = {
    "changed file is in a high-risk path.",
    "high-risk path detected for review attention.",
    "potential tainted input path needs validation review.",
    "user-controlled input appears near a risky sink.",
}


def _safe_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: object) -> str:
    return str(value or "").strip()


def _finding_id(item: dict[str, Any]) -> str:
    identity = {
        "root_cause": item.get("root_cause"),
        "path": item.get("path"),
        "line": item.get("line_start") or item.get("line"),
        "message": item.get("message"),
    }
    return "finding-" + hashlib.sha256(json.dumps(identity, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _normalize(item: dict[str, Any], source: str) -> dict[str, Any]:
    finding = dict(item)
    finding["severity"] = _text(finding.get("severity") or "unknown").lower()
    capability = _text(finding.get("capability") or finding.get("category") or "general")
    finding.setdefault("source", source)
    finding.setdefault("capability", capability)
    finding.setdefault("category", capability)
    finding.setdefault("officer", OFFICER_BY_CAPABILITY.get(capability, "Analyst"))
    finding.setdefault("root_cause", capability or "general-review")
    finding.setdefault("confidence", 0.5)
    finding.setdefault("direct_evidence", False)
    finding.setdefault("falsifiers_checked", [])
    finding.setdefault("line_start", finding.get("line"))
    finding.setdefault("line_end", finding.get("line_start") or finding.get("line"))
    finding["finding_id"] = _finding_id(finding)
    return finding


def _canonical_dispositions(
    admitted: list[dict[str, Any]],
    advisory: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
) -> dict[str, str]:
    """Return one Judge disposition per canonical finding.

    Source-level duplicates remain available in the raw and rejected evidence,
    while their canonical identity keeps the strongest adjudicated state.
    """

    dispositions = {item["finding_id"]: "rejected" for item in rejected}
    dispositions.update({item["finding_id"]: "advisory" for item in advisory})
    dispositions.update({item["finding_id"]: "admitted" for item in admitted})
    return dispositions


def _canonical_key(item: dict[str, Any]) -> tuple[str, str, int | None, str]:
    return (
        _text(item.get("root_cause")),
        _text(item.get("path")),
        item.get("line_start") or item.get("line"),
        _text(item.get("message")).lower(),
    )


def _raw_candidates(
    repository_review: dict[str, Any],
    diff: dict[str, Any],
    capabilities: dict[str, Any],
    cpl: dict[str, Any],
    offline: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    sources = (
        ("repository", _safe_list(_safe_dict(repository_review.get("evidence")).get("findings"))),
        ("diff", _safe_list(_safe_dict(diff.get("evidence")).get("findings"))),
        ("capability", _safe_list(capabilities.get("findings"))),
        ("offline-officer", _safe_list(offline.get("findings"))),
        ("cpl-model", _safe_list(cpl.get("actionable_findings"))),
        ("cpl-model-advisory", _safe_list(cpl.get("advisory_findings"))),
        ("cpl-model-confirmation", _safe_list(cpl.get("confirmed_findings"))),
        ("cpl-model-unconfirmed", _safe_list(cpl.get("unconfirmed_findings"))),
    )
    for source, rows in sources:
        candidates.extend(_normalize(item, source) for item in rows if isinstance(item, dict))
    return candidates


def _promotion_keys(intelligence: dict[str, Any]) -> set[tuple[str, str, int | None, str]]:
    return {
        _canonical_key(_normalize(item, "review-intelligence"))
        for item in _safe_list(intelligence.get("promoted_findings"))
        if isinstance(item, dict)
    }


def _adjudicate(
    candidates: list[dict[str, Any]],
    intelligence: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    promoted = _promotion_keys(intelligence)
    admitted: list[dict[str, Any]] = []
    advisory: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int | None, str]] = set()

    # Strong deterministic field investigations are considered first so broad
    # scanner signals become confirmation rather than duplicate actions.
    candidates = sorted(candidates, key=lambda row: row.get("source") != "offline-officer")
    for finding in candidates:
        key = _canonical_key(finding)
        severity = _text(finding.get("severity")).lower()
        message = _text(finding.get("message")).lower()
        source = _text(finding.get("source"))
        direct = bool(finding.get("direct_evidence"))
        generic_risk = message in _GENERIC_RISK_MESSAGES or finding.get("admission_hint") == "risk_trigger"

        if source == "cpl-model-confirmation":
            finding["admission"] = "confirmation"
            finding["gates_verdict"] = False
            advisory.append(finding)
            continue

        if key in seen:
            finding["admission"] = "duplicate"
            finding["gates_verdict"] = False
            rejected.append(finding)
            continue

        if generic_risk:
            finding["admission"] = "risk_trigger"
            finding["gates_verdict"] = False
            advisory.append(finding)
            seen.add(key)
            continue

        actionable = severity in {"blocker", "major"} and (
            source == "offline-officer"
            or source == "repository"
            or source == "cpl-model"
            or key in promoted
            or (direct and bool(finding.get("evidence_ref")))
            or finding.get("root_cause") == "proof-gap"
        )
        if actionable:
            finding["admission"] = "actionable"
            finding["gates_verdict"] = True
            admitted.append(finding)
            seen.add(key)
        elif severity in {"minor", "note"}:
            finding["admission"] = "advisory"
            finding["gates_verdict"] = False
            advisory.append(finding)
            seen.add(key)
        else:
            finding["admission"] = "rejected_unsubstantiated"
            finding["gates_verdict"] = False
            rejected.append(finding)
            seen.add(key)
    return admitted, advisory, rejected


def _assurances(
    changed_files: list[str],
    diff: dict[str, Any],
    offline: dict[str, Any],
    standard: dict[str, Any],
) -> list[dict[str, Any]]:
    readable = set(_safe_list(offline.get("readable_changed_files")))
    unavailable = set(_safe_list(offline.get("unavailable_changed_files")))
    coverage_by_officer = {
        _text(item.get("officer"))
        for item in _safe_list(offline.get("coverage"))
        if isinstance(item, dict) and item.get("status") == "completed"
    }
    assurances: list[dict[str, Any]] = []
    for finding in _safe_list(_safe_dict(diff.get("evidence")).get("findings")):
        if not isinstance(finding, dict) or _text(finding.get("message")).lower() not in _GENERIC_RISK_MESSAGES:
            continue
        path = _text(finding.get("path"))
        required = ["Scout", "Engineer", "Medic", "Mechanic"]
        satisfied = path in readable and set(required).issubset(coverage_by_officer)
        assurances.append({
            "assurance_id": "assurance-" + hashlib.sha256(f"high-risk:{path}".encode()).hexdigest()[:16],
            "kind": "high_risk_change_review",
            "path": path,
            "required_assurance": "deterministic_officer_coverage",
            "required_officers": required,
            "status": "satisfied" if satisfied else "unresolved",
            "gates_verdict": not satisfied,
            "evidence": "Scout mapped the path and Engineer, Medic and Mechanic completed bounded deterministic checks." if satisfied else "Changed high-risk content was unavailable or required officer coverage did not complete.",
        })
    for index, blocker in enumerate(_safe_list(standard.get("blockers"))):
        assurances.append({
            "assurance_id": f"standard-{index}",
            "kind": "engineering_standard",
            "required_assurance": "repository_standard_proof",
            "status": "unresolved",
            "gates_verdict": True,
            "evidence": _text(blocker),
        })
    if unavailable and not assurances:
        # Missing ordinary files are recorded, but do not invent a blocker
        # unless another policy explicitly requires their assurance.
        assurances.append({
            "assurance_id": "unavailable-scope",
            "kind": "scope_visibility",
            "required_assurance": "none",
            "status": "advisory",
            "gates_verdict": False,
            "evidence": f"Unavailable changed paths: {', '.join(sorted(unavailable))}",
        })
    return assurances


def _status(findings: list[dict[str, Any]]) -> str:
    if any(item.get("severity") == "blocker" for item in findings):
        return "block"
    if any(item.get("severity") == "major" for item in findings):
        return "needs_work"
    return "pass"


def _officer_reports(
    candidates: list[dict[str, Any]],
    admitted: list[dict[str, Any]],
    advisory: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    assurances: list[dict[str, Any]],
    offline: dict[str, Any],
    cpl: dict[str, Any],
) -> list[dict[str, Any]]:
    by_officer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        by_officer[_text(item.get("officer") or "Analyst")].append(item)
    model_support = _safe_list(cpl.get("passes"))
    reports: list[dict[str, Any]] = []
    for officer in OFFICER_ORDER:
        claims = by_officer.get(officer, [])
        officer_admitted = [item for item in admitted if item.get("officer") == officer]
        officer_advisory = [item for item in advisory if item.get("officer") == officer]
        officer_rejected = [item for item in rejected if item.get("officer") == officer]
        officer_assurance = [item for item in assurances if officer in _safe_list(item.get("required_officers"))]
        reports.append({
            "agent": officer.lower(),
            "officer": officer,
            "status": _status(officer_admitted),
            "summary": f"{officer} completed deterministic evidence duties with {len(officer_admitted)} admitted, {len(officer_advisory)} advisory and {len(officer_rejected)} rejected claim(s).",
            "findings": officer_admitted,
            "claims_reviewed": len(claims),
            "admitted_findings": officer_admitted,
            "advisory_findings": officer_advisory,
            "rejected_findings": officer_rejected,
            "required_assurances": officer_assurance,
            "evidence_refs": sorted({_text(item.get("evidence_ref")) for item in claims if item.get("evidence_ref")}),
            "falsifiers_checked": [check for item in claims for check in _safe_list(item.get("falsifiers_checked"))],
            "unresolved_questions": [],
            "model_support": [item for item in model_support if _text(item.get("supported_officer")).lower() == officer.lower()],
            "model_support_status": cpl.get("status", "not_deployed"),
            "confidence": round(max([float(item.get("confidence") or 0.0) for item in officer_admitted] or [0.76]), 2),
            "commanded_by": "cpl",
            "cpl_support": [],
        })

    # Analyst, Challenger, Judge and Hermes report on the whole ledger rather
    # than pretending their work is a separate scanner signal.
    report_by_name = {item["officer"]: item for item in reports}
    roots = defaultdict(list)
    for item in admitted:
        roots[_text(item.get("root_cause"))].append(item["finding_id"])
    report_by_name["Analyst"]["root_cause_groups"] = dict(roots)
    report_by_name["Analyst"]["summary"] = f"Analyst reconciled {len(admitted)} admitted finding(s) into {len(roots)} root-cause group(s)."
    report_by_name["Challenger"]["challenges"] = [
        {"finding_id": item["finding_id"], "result": "survived", "falsifiers_checked": item.get("falsifiers_checked", [])}
        for item in admitted
    ] + [
        {"finding_id": item["finding_id"], "result": item.get("admission")}
        for item in [*advisory, *rejected]
    ]
    report_by_name["Challenger"]["summary"] = f"Challenger attacked {len(candidates)} candidate claim(s); only {len(admitted)} survived as actionable."
    dispositions = _canonical_dispositions(admitted, advisory, rejected)
    report_by_name["Judge"]["admission_ledger"] = {
        state: [finding_id for finding_id, disposition in dispositions.items() if disposition == state]
        for state in ("admitted", "advisory", "rejected")
    }
    report_by_name["Judge"]["summary"] = "Judge admitted only grounded actionable claims and explicit unresolved assurance obligations."
    report_by_name["Quartermaster"]["capacity"] = {
        "deterministic_investigation": "available",
        "model_support": cpl.get("status", "not_deployed"),
        "executed_project_code": offline.get("executed_project_code", False),
    }
    report_by_name["Scout"]["coverage"] = offline.get("coverage", [])
    report_by_name["Hermes"]["summary"] = "Hermes prepared a traceable transaction ledger linking orders, evidence, admission and verdict."
    return reports


def _transactions(
    changed_files: list[str],
    candidates: list[dict[str, Any]],
    admitted: list[dict[str, Any]],
    advisory: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    assurances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [{
        "transaction": "mission_created",
        "sender": "Sergeant",
        "recipient": "Cpl",
        "scope": changed_files,
    }]
    rows.extend({
        "transaction": "claim_collected",
        "sender": item.get("officer"),
        "recipient": "Analyst",
        "finding_id": item["finding_id"],
        "evidence_ref": item.get("evidence_ref"),
    } for item in candidates)
    disposition = _canonical_dispositions(admitted, advisory, rejected)
    rows.extend({
        "transaction": "claim_adjudicated",
        "sender": "Judge",
        "recipient": "Cpl",
        "finding_id": finding_id,
        "disposition": result,
    } for finding_id, result in disposition.items())
    rows.extend({
        "transaction": "assurance_updated",
        "sender": "Judge",
        "recipient": "Cpl",
        "assurance_id": item.get("assurance_id"),
        "status": item.get("status"),
    } for item in assurances)
    return rows


def run_officer_council(
    root: str | Path,
    changed_files: Iterable[str],
    *,
    repository_review: dict[str, Any],
    diff: dict[str, Any],
    capabilities: dict[str, Any],
    intelligence: dict[str, Any],
    standard: dict[str, Any],
    cpl: dict[str, Any],
) -> dict[str, Any]:
    changed = sorted({str(item) for item in changed_files if str(item)})
    offline = run_offline_investigations(root, changed)
    candidates = _raw_candidates(repository_review, diff, capabilities, cpl, offline)
    admitted, advisory, rejected = _adjudicate(candidates, intelligence)
    assurances = _assurances(changed, diff, offline, standard)
    unresolved = [item for item in assurances if item.get("gates_verdict") and item.get("status") != "satisfied"]
    if any(item.get("severity") == "blocker" for item in admitted):
        verdict = "BLOCK"
    elif any(item.get("severity") == "major" for item in admitted) or unresolved:
        verdict = "NEEDS WORK"
    else:
        verdict = "PASS"
    reports = _officer_reports(candidates, admitted, advisory, rejected, assurances, offline, cpl)
    campaign = build_cpl_campaign(
        root,
        changed,
        officer_reports=reports,
        admitted=admitted,
        advisory=advisory,
        rejected=rejected,
        assurances=assurances,
        cpl=cpl,
        offline=offline,
    )
    transactions = _transactions(changed, candidates, admitted, advisory, rejected, assurances)
    transactions.extend(campaign.get("transactions", []))
    transactions.append({
        "transaction": "ground_report_delivered",
        "sender": "Cpl",
        "recipient": "Sergeant",
        "verdict_recommendation": verdict,
        "admitted_findings": len(admitted),
        "unresolved_assurances": len(unresolved),
    })
    return {
        "schema_version": "sergeant.officer-council.v1",
        "mode": "deterministic_officer_formation",
        "complete": True,
        "model_support_status": cpl.get("status", "not_deployed"),
        "models_required": False,
        "verdict": verdict,
        "raw_findings": candidates,
        "admitted_findings": admitted,
        "actionable_findings": admitted,
        "advisory_findings": advisory,
        "rejected_findings": rejected,
        "required_assurances": assurances,
        "unresolved_assurances": unresolved,
        "reports": reports,
        "transactions": transactions,
        "offline_investigation": offline,
        "campaign": campaign,
        "workspace_ready": True,
        "private_force": campaign.get("private_force", {}),
        "workspace_adapter_status": campaign.get("adapter_status", {}).get("workspace"),
        "research_adapter_status": campaign.get("adapter_status", {}).get("research"),
        "required_actions": [
            f"Resolve {item.get('officer')} {item.get('severity')} finding at {item.get('evidence_ref')}: {item.get('message')}"
            for item in admitted
            if item.get("severity") in {"blocker", "major"}
        ] + [
            f"Satisfy {item.get('required_assurance')} for {item.get('path') or item.get('kind')}."
            for item in unresolved
        ],
        "rule": "Permanent officers investigate and Judge admits evidence without models; model and lookup results can amplify the same packets but cannot replace them.",
    }
