"""Tier 6 squad intelligence with Cpl-led officer amplification.

Sergeant remains the final reviewer. Permanent officers produce focused reports.
Cpl is the senior field-reasoning layer: it shares grounded mission intelligence
with the squad and assigns model-powered support bots to the officers whose
specialities match the mission. Sergeant weighs the resulting evidence and
issues one command summary.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

AGENT_ORDER = ["quartermaster", "scout", "engineer", "medic", "mechanic", "analyst", "challenger", "archivist", "judge", "hermes"]


@dataclass(frozen=True)
class AgentReport:
    agent: str
    role: str
    status: str
    summary: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.7
    commanded_by: str = "cpl"
    cpl_support: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _safe_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _capability_findings(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return _safe_list(_safe_dict(packet.get("capability_review")).get("findings"))


def _ranked_findings(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return _safe_list(_safe_dict(packet.get("review_intelligence")).get("ranked_findings"))


def _classified_findings(evidence_consensus: dict[str, Any]) -> list[dict[str, Any]]:
    return _safe_list(evidence_consensus.get("classified_findings"))


def _by_capability(findings: list[dict[str, Any]], names: set[str]) -> list[dict[str, Any]]:
    return [item for item in findings if isinstance(item, dict) and str(item.get("capability") or item.get("category") or "") in names]


def _status(findings: list[dict[str, Any]]) -> str:
    if any(str(item.get("severity") or item.get("verdict") or "").upper() in {"BLOCK", "BLOCKER"} for item in findings if isinstance(item, dict)):
        return "block"
    if findings:
        return "needs_work"
    return "pass"


def _verdict_status(value: object) -> str:
    verdict = str(value or "PASS").upper().replace(" ", "_")
    if verdict in {"BLOCK", "BLOCKER", "REQUEST_CHANGES"}:
        return "block"
    if verdict in {"NEEDS_WORK", "COMMENT"}:
        return "needs_work"
    return "pass"


def _worst_status(*statuses: str) -> str:
    rank = {"pass": 0, "needs_work": 1, "block": 2}
    return max(statuses, key=lambda item: rank.get(item, 1))


def _confidence(findings: list[dict[str, Any]], base: float = 0.72) -> float:
    values = [float(item.get("confidence") or base) for item in findings if isinstance(item, dict)]
    if not values:
        return base
    return round(min(0.99, max(0.1, sum(values) / len(values))), 2)


def _cpl_review(packet: dict[str, Any]) -> dict[str, Any]:
    return _safe_dict(packet.get("cpl_review") or packet.get("semantic_review"))


def _shared_cpl_support(cpl: dict[str, Any]) -> list[dict[str, Any]]:
    if not cpl:
        return []
    passes = _safe_list(cpl.get("passes"))
    general = _safe_dict(passes[0]) if passes else {}
    route = _safe_dict(cpl.get("route"))
    return [{
        "kind": "shared_field_intelligence",
        "commanded_by": "cpl",
        "status": cpl.get("status", "unknown"),
        "model": general.get("model") or route.get("model"),
        "provider": general.get("provider") or route.get("provider"),
        "verdict": general.get("verdict") or cpl.get("verdict", "PASS"),
        "confidence": cpl.get("confidence", 0.0),
        "summary": general.get("summary") or cpl.get("summary", ""),
        "findings": general.get("findings", []),
        "coverage": cpl.get("coverage", {}),
        "unanswered_questions": cpl.get("unanswered_questions", []),
    }]


def _targeted_cpl_support(cpl: dict[str, Any], officer: str) -> list[dict[str, Any]]:
    plans = {
        str(item.get("specialist")): item
        for item in _safe_list(cpl.get("reasoning_plan"))
        if isinstance(item, dict)
    }
    support: list[dict[str, Any]] = []
    for item in _safe_list(cpl.get("passes")):
        if not isinstance(item, dict):
            continue
        specialist = str(item.get("specialist") or "")
        plan = _safe_dict(plans.get(specialist))
        if str(plan.get("officer") or "").lower() != officer.lower():
            continue
        support.append({
            "kind": "officer_support_bot",
            "commanded_by": "cpl",
            "supported_officer": plan.get("officer"),
            "officer_role": plan.get("officer_role"),
            "specialist": specialist,
            "support_unit": plan.get("title") or item.get("specialist_title"),
            "mission": plan.get("mission"),
            "model": item.get("model") or plan.get("model"),
            "provider": item.get("provider"),
            "verdict": item.get("verdict"),
            "confidence": item.get("confidence", 0.0),
            "findings": _safe_list(item.get("findings")),
        })
    return support


def _support_findings(support: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        finding
        for unit in support
        for finding in _safe_list(unit.get("findings"))
        if isinstance(finding, dict)
    ]


def _support_status(support: list[dict[str, Any]]) -> str:
    return _worst_status(*[_verdict_status(unit.get("verdict")) for unit in support]) if support else "pass"


def _officer_report(
    agent: str,
    role: str,
    summary: str,
    findings: list[dict[str, Any]],
    base_confidence: float,
    cpl: dict[str, Any],
    *,
    base_status: str | None = None,
) -> AgentReport:
    targeted = _targeted_cpl_support(cpl, agent)
    support = _shared_cpl_support(cpl) + targeted
    amplified_findings = (findings + _support_findings(targeted))[:8]
    status = _worst_status(base_status or _status(findings), _support_status(targeted))
    support_confidences = [float(unit.get("confidence") or base_confidence) for unit in targeted]
    confidence_values = [_confidence(findings, base_confidence), *support_confidences]
    confidence = round(sum(confidence_values) / max(1, len(confidence_values)), 2)
    suffix = f" Cpl attached {len(targeted)} targeted model support unit(s)." if targeted else " Cpl shared grounded field intelligence."
    return AgentReport(agent, role, status, summary + suffix, amplified_findings, confidence, "cpl", support)


def build_squad_reports(review_packet: dict[str, Any], evidence_consensus: dict[str, Any], learning: dict[str, Any] | None = None, graduation: dict[str, Any] | None = None) -> list[dict[str, object]]:
    capability = _capability_findings(review_packet)
    ranked = _ranked_findings(review_packet)
    classified = _classified_findings(evidence_consensus)
    learning = learning or {}
    graduation = graduation or {}
    repo = _safe_dict(review_packet.get("repository_review"))
    cpl = _cpl_review(review_packet)
    learning_candidates = _safe_list(_safe_dict(learning.get("learning")).get("candidates"))

    reports = [
        _officer_report("quartermaster", "index/cache supplier", "Prepared shared review context and mission loadout for the squad.", [{"files_reviewed": len(repo.get("findings", []))}], 0.75, cpl, base_status="pass"),
        _officer_report("scout", "repository scanner", "Mapped repository and changed-file signals for all deployed officers.", capability[:8], _confidence(capability), cpl),
        _officer_report("engineer", "architecture, correctness, and API contracts", "Checked technical construction, architecture boundaries, API contracts, tests, and dependency impact.", _by_capability(capability, {"architecture", "api_contract", "cross_file", "call_graph"})[:8], 0.78, cpl),
        _officer_report("medic", "security, diagnosis, and safe remediation", "Checked unsafe data flow, security-sensitive patterns, containment, regression risk, and repair safety.", _by_capability(capability, {"security_taint", "data_flow"})[:8], 0.78, cpl),
        _officer_report("mechanic", "performance and concurrency", "Checked runtime cost, blocking patterns, and race-risk signals.", _by_capability(capability, {"performance", "concurrency"})[:8], 0.74, cpl),
        _officer_report("analyst", "root cause grouping", "Grouped findings into root causes and ranked review priority.", ranked[:8], _confidence(ranked, 0.76), cpl),
        _officer_report("challenger", "second-opinion pressure test", "Compared Sergeant findings with external evidence and challenged disagreement.", classified[:8], _confidence(classified, 0.76), cpl),
        _officer_report("archivist", "verified learning memory", "Prepared verified learning candidates from human outcomes.", learning_candidates[:8], 0.82, cpl, base_status="pass" if not learning_candidates else "needs_work"),
        _officer_report("judge", "graduation benchmark", "Scored officer, weapon, and mission trust against reference evidence.", [{"verdict": graduation.get("verdict"), "delta": graduation.get("delta")}], 0.8, cpl, base_status="pass" if graduation.get("verdict") in {"GRADUATED", "TRUSTED_WITH_WATCH"} else "needs_work"),
        _officer_report("hermes", "accurate delivery officer", "Prepared evidence-linked app, GitHub, CLI, and IDE-ready mission output.", [{"delivery": "app_bridge", "external_tools_are_witnesses": True}], 0.86, cpl, base_status="pass"),
    ]
    return [report.to_dict() for report in reports]


def command_summary(reports: list[dict[str, object]]) -> dict[str, object]:
    blocking = [report for report in reports if report.get("status") == "block"]
    needs_work = [report for report in reports if report.get("status") == "needs_work"]
    if blocking:
        verdict = "BLOCK"
    elif needs_work:
        verdict = "NEEDS_WORK"
    else:
        verdict = "PASS"
    return {
        "verdict": verdict,
        "agents": [report.get("agent") for report in reports],
        "blocking_agents": [report.get("agent") for report in blocking],
        "needs_work_agents": [report.get("agent") for report in needs_work],
        "rule": "Specialists advise. Cpl amplifies the permanent officers. Sergeant commands the final review.",
    }


def run_squad_review(review_packet: dict[str, Any], evidence_consensus: dict[str, Any], learning: dict[str, Any] | None = None, graduation: dict[str, Any] | None = None) -> dict[str, object]:
    reports = build_squad_reports(review_packet, evidence_consensus, learning, graduation)
    cpl = _cpl_review(review_packet)
    return {
        "summary": command_summary(reports),
        "cpl_command": {
            "role": "senior field reasoning and officer amplification",
            "status": cpl.get("status", "not_deployed"),
            "verdict": cpl.get("verdict", "PASS"),
            "confidence": cpl.get("confidence", 0.0),
            "route": cpl.get("route", {}),
            "reasoning_plan": cpl.get("reasoning_plan", []),
        },
        "reports": reports,
    }
