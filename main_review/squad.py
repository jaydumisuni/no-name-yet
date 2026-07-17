"""Tier 6 squad intelligence with Cpl-led officer amplification.

Permanent officers keep their doctrine, experience, evidence duties, and reports.
Cpl supplies shared field intelligence, an elastic model council, targeted support
bots, and improved instructions without replacing the squad.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

AGENT_ORDER = ["quartermaster", "scout", "engineer", "medic", "mechanic", "analyst", "challenger", "archivist", "judge", "hermes"]

OFFICER_ROLES = {
    "quartermaster": "capacity, budget, provider and loadout control",
    "scout": "repository mapping, scope and evidence inventory",
    "engineer": "correctness, architecture, contracts and test impact",
    "medic": "security, privacy, trust boundaries and safe recovery",
    "mechanic": "runtime, concurrency, performance and state lifecycle",
    "analyst": "root-cause reconciliation and alternative hypotheses",
    "challenger": "falsification, bypasses and negative controls",
    "archivist": "verified experience and recurrence provenance",
    "judge": "finding admission, assurance and verdict recommendation",
    "hermes": "traceable evidence and command transactions",
}


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
    return "needs_work" if findings else "pass"


def _verdict_status(value: object) -> str:
    verdict = str(value or "PASS").upper().replace(" ", "_")
    if verdict in {"BLOCK", "BLOCKER", "REQUEST_CHANGES"}:
        return "block"
    return "needs_work" if verdict in {"NEEDS_WORK", "COMMENT"} else "pass"


def _worst_status(*statuses: str) -> str:
    rank = {"pass": 0, "needs_work": 1, "block": 2}
    return max(statuses, key=lambda item: rank.get(item, 1))


def _confidence(findings: list[dict[str, Any]], base: float = 0.72) -> float:
    values = [float(item.get("confidence") or base) for item in findings if isinstance(item, dict)]
    return round(min(0.99, max(0.1, sum(values) / len(values))), 2) if values else base


def _cpl_review(packet: dict[str, Any]) -> dict[str, Any]:
    return _safe_dict(packet.get("cpl_review") or packet.get("semantic_review"))


def _shared_cpl_support(cpl: dict[str, Any]) -> list[dict[str, Any]]:
    if not cpl:
        return []
    passes = _safe_list(cpl.get("passes"))
    general = _safe_dict(passes[0]) if passes else {}
    route = _safe_dict(cpl.get("route"))
    council = _safe_dict(cpl.get("council"))
    return [
        {
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
        },
        {
            "kind": "cpl_council_state",
            "commanded_by": "cpl",
            "mode": council.get("mode", "not_deployed"),
            "round_count": council.get("round_count", 0),
            "member_count": council.get("member_count", 0),
            "agreement": council.get("agreement", 0.0),
            "model_independence": council.get("model_independence", 0.0),
            "complete": council.get("complete", False),
            "final_gaps": council.get("final_gaps", []),
            "recurrences": cpl.get("recurrences", []),
        },
    ]


def _officer_experience(cpl: dict[str, Any], officer: str) -> list[dict[str, Any]]:
    experience = _safe_dict(cpl.get("experience"))
    events = [
        item for item in _safe_list(experience.get("events"))
        if isinstance(item, dict) and item.get("subject_type") == "officer" and str(item.get("subject_id", "")).lower() == officer.lower()
    ]
    profile = _safe_dict(experience.get("profiles")).get(f"officer:{officer}")
    instructions = [
        item for item in _safe_list(_safe_dict(cpl.get("council")).get("officer_instructions"))
        if isinstance(item, dict) and str(item.get("to_officer", "")).lower() == officer.lower()
    ]
    if not events and not profile and not instructions:
        return []
    return [{
        "kind": "officer_experience",
        "officer": officer,
        "verified_and_rejected_events": events,
        "profile": profile or {},
        "cpl_instructions": instructions,
        "anti_repeat_rule": experience.get("anti_repeat_rule"),
    }]


def _targeted_cpl_support(cpl: dict[str, Any], officer: str) -> list[dict[str, Any]]:
    plans = {str(item.get("specialist")): item for item in _safe_list(cpl.get("reasoning_plan")) if isinstance(item, dict)}
    support: list[dict[str, Any]] = []
    for item in _safe_list(cpl.get("passes")):
        if not isinstance(item, dict):
            continue
        specialist = str(item.get("specialist") or "")
        plan = _safe_dict(plans.get(specialist))
        supported_officer = item.get("supported_officer") or plan.get("officer")
        if str(supported_officer or "").lower() != officer.lower():
            continue
        support.append({
            "kind": "officer_support_bot",
            "commanded_by": "cpl",
            "supported_officer": supported_officer,
            "officer_role": plan.get("officer_role"),
            "specialist": specialist,
            "support_unit": plan.get("title") or item.get("specialist_title"),
            "mission": plan.get("mission") or _safe_dict(item.get("instruction_received")).get("instruction"),
            "model": item.get("model") or plan.get("model"),
            "provider": item.get("provider"),
            "council_round": item.get("council_round", 1),
            "council_member_role": item.get("council_member_role"),
            "admission": item.get("admission", "core_member"),
            "verdict": item.get("verdict"),
            "confidence": item.get("confidence", 0.0),
            "resolution_status": item.get("resolution_status"),
            "findings": _safe_list(item.get("findings")),
        })
    return [*_officer_experience(cpl, officer), *support]


def _support_findings(support: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [finding for unit in support for finding in _safe_list(unit.get("findings")) if isinstance(finding, dict)]


def _support_status(support: list[dict[str, Any]]) -> str:
    verdicts = [_verdict_status(unit.get("verdict")) for unit in support if unit.get("kind") == "officer_support_bot"]
    return _worst_status(*verdicts) if verdicts else "pass"


def _officer_report(agent: str, role: str, summary: str, findings: list[dict[str, Any]], base_confidence: float, cpl: dict[str, Any], *, base_status: str | None = None) -> AgentReport:
    targeted = _targeted_cpl_support(cpl, agent)
    support = _shared_cpl_support(cpl) + targeted
    amplified_findings = (findings + _support_findings(targeted))[:8]
    status = _worst_status(base_status or _status(findings), _support_status(targeted))
    support_confidences = [float(unit.get("confidence") or base_confidence) for unit in targeted if unit.get("kind") == "officer_support_bot"]
    values = [_confidence(findings, base_confidence), *support_confidences]
    confidence = round(sum(values) / max(1, len(values)), 2)
    bot_count = sum(unit.get("kind") == "officer_support_bot" for unit in targeted)
    memory_count = sum(unit.get("kind") == "officer_experience" for unit in targeted)
    suffix = f" Cpl attached {bot_count} model support unit(s) and {memory_count} specialist experience packet(s)."
    return AgentReport(agent, role, status, summary + suffix, amplified_findings, confidence, "cpl", support)


def build_squad_reports(review_packet: dict[str, Any], evidence_consensus: dict[str, Any], learning: dict[str, Any] | None = None, graduation: dict[str, Any] | None = None) -> list[dict[str, object]]:
    formation = _safe_dict(review_packet.get("officer_council"))
    formation_reports = _safe_list(formation.get("reports"))
    if formation_reports:
        learning = learning or {}
        graduation = graduation or {}
        learning_payload = _safe_dict(learning.get("learning"))
        learning_candidates = _safe_list(learning_payload.get("candidates"))
        reports: list[dict[str, object]] = []
        for item in formation_reports:
            if not isinstance(item, dict):
                continue
            report: dict[str, object] = {
                **item,
                "role": item.get("role") or OFFICER_ROLES.get(str(item.get("agent") or ""), "permanent officer"),
            }
            officer = str(item.get("officer") or item.get("agent") or "").lower()
            if officer == "archivist":
                report["learning"] = learning_payload
                report["learning_candidates"] = learning_candidates
                report["findings"] = [*_safe_list(item.get("findings")), *learning_candidates][:8]
            elif officer == "judge":
                graduation_evidence = {
                    "verdict": graduation.get("verdict"),
                    "delta": graduation.get("delta"),
                }
                report["graduation"] = graduation
                report["findings"] = [*_safe_list(item.get("findings")), graduation_evidence][:8]
            reports.append(report)
        return reports

    capability = _capability_findings(review_packet)
    ranked = _ranked_findings(review_packet)
    classified = _classified_findings(evidence_consensus)
    learning = learning or {}
    graduation = graduation or {}
    repo = _safe_dict(review_packet.get("repository_review"))
    cpl = _cpl_review(review_packet)
    learning_candidates = _safe_list(_safe_dict(learning.get("learning")).get("candidates"))
    reports = [
        _officer_report("quartermaster", "index/cache supplier", "Prepared shared context, council capacity, models, and mission loadout.", [{"files_reviewed": len(repo.get("findings", []))}], 0.75, cpl, base_status="pass"),
        _officer_report("scout", "repository scanner", "Mapped repository and changed-file signals for the deployed squad.", capability[:8], _confidence(capability), cpl),
        _officer_report("engineer", "architecture, correctness, and API contracts", "Checked construction, architecture boundaries, contracts, tests, and dependency impact.", _by_capability(capability, {"architecture", "api_contract", "cross_file", "call_graph"})[:8], 0.78, cpl),
        _officer_report("medic", "security, diagnosis, and safe remediation", "Checked unsafe flow, containment, repair, rollback, and regression risk.", _by_capability(capability, {"security_taint", "data_flow"})[:8], 0.78, cpl),
        _officer_report("mechanic", "performance and concurrency", "Checked runtime cost, resource lifetime, blocking, and race-risk signals.", _by_capability(capability, {"performance", "concurrency"})[:8], 0.74, cpl),
        _officer_report("analyst", "root cause grouping", "Grouped evidence into root causes, options, disagreement, and review priority.", ranked[:8], _confidence(ranked, 0.76), cpl),
        _officer_report("challenger", "second-opinion pressure test", "Attacked preferred explanations and compared independent evidence.", classified[:8], _confidence(classified, 0.76), cpl),
        _officer_report("archivist", "verified learning memory", "Prepared only verified or rejected learning outcomes for durable memory.", learning_candidates[:8], 0.82, cpl, base_status="pass" if not learning_candidates else "needs_work"),
        _officer_report("judge", "graduation benchmark", "Scored officer, model, weapon, and mission trust against proven outcomes.", [{"verdict": graduation.get("verdict"), "delta": graduation.get("delta")}], 0.8, cpl, base_status="pass" if graduation.get("verdict") in {"GRADUATED", "TRUSTED_WITH_WATCH"} else "needs_work"),
        _officer_report("hermes", "accurate delivery officer", "Prepared evidence-linked app, GitHub, CLI, and IDE mission output.", [{"delivery": "app_bridge", "external_tools_are_witnesses": True}], 0.86, cpl, base_status="pass"),
    ]
    return [report.to_dict() for report in reports]


def command_summary(reports: list[dict[str, object]]) -> dict[str, object]:
    blocking = [report for report in reports if report.get("status") == "block"]
    needs_work = [report for report in reports if report.get("status") == "needs_work"]
    verdict = "BLOCK" if blocking else "NEEDS_WORK" if needs_work else "PASS"
    return {
        "verdict": verdict,
        "agents": [report.get("agent") for report in reports],
        "blocking_agents": [report.get("agent") for report in blocking],
        "needs_work_agents": [report.get("agent") for report in needs_work],
        "rule": "Specialists advise. Cpl amplifies through councils, verified experience, and evidence-driven rebriefs. Permanent officers own specialist truth. Sergeant commands the final review.",
    }


def run_squad_review(review_packet: dict[str, Any], evidence_consensus: dict[str, Any], learning: dict[str, Any] | None = None, graduation: dict[str, Any] | None = None) -> dict[str, object]:
    reports = build_squad_reports(review_packet, evidence_consensus, learning, graduation)
    cpl = _cpl_review(review_packet)
    return {
        "summary": command_summary(reports),
        "cpl_command": {
            "role": "senior field reasoning, council command, officer amplification, and command learning",
            "status": cpl.get("status", "not_deployed"),
            "verdict": cpl.get("verdict", "PASS"),
            "confidence": cpl.get("confidence", 0.0),
            "route": cpl.get("route", {}),
            "reasoning_plan": cpl.get("reasoning_plan", []),
            "council": cpl.get("council", {}),
            "memory_checked": cpl.get("memory_checked", False),
            "recurrences": cpl.get("recurrences", []),
        },
        "reports": reports,
    }
