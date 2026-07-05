"""Tier 6 squad intelligence for Sergeant.

Sergeant remains the final reviewer. The squad is a set of specialist agents
that produce focused reports. Sergeant weighs their evidence and issues one
command summary.
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


def _confidence(findings: list[dict[str, Any]], base: float = 0.72) -> float:
    values = [float(item.get("confidence") or base) for item in findings if isinstance(item, dict)]
    if not values:
        return base
    return round(min(0.99, max(0.1, sum(values) / len(values))), 2)


def build_squad_reports(review_packet: dict[str, Any], evidence_consensus: dict[str, Any], learning: dict[str, Any] | None = None, graduation: dict[str, Any] | None = None) -> list[dict[str, object]]:
    capability = _capability_findings(review_packet)
    ranked = _ranked_findings(review_packet)
    classified = _classified_findings(evidence_consensus)
    learning = learning or {}
    graduation = graduation or {}
    repo = _safe_dict(review_packet.get("repository_review"))
    standard = _safe_dict(review_packet.get("standard"))

    reports = [
        AgentReport("quartermaster", "index/cache supplier", "pass", "Prepared shared review context for the squad.", [{"files_reviewed": len(repo.get("findings", []))}], 0.75),
        AgentReport("scout", "repository scanner", _status(capability), "Mapped repository and changed-file signals.", capability[:8], _confidence(capability)),
        AgentReport("engineer", "architecture and API contracts", _status(_by_capability(capability, {"architecture", "api_contract", "cross_file", "call_graph"})), "Checked architecture boundaries, API contracts, and dependency impact.", _by_capability(capability, {"architecture", "api_contract", "cross_file", "call_graph"})[:8], 0.78),
        AgentReport("medic", "security and taint analysis", _status(_by_capability(capability, {"security_taint", "data_flow"})), "Checked unsafe data flow and security-sensitive patterns.", _by_capability(capability, {"security_taint", "data_flow"})[:8], 0.78),
        AgentReport("mechanic", "performance and concurrency", _status(_by_capability(capability, {"performance", "concurrency"})), "Checked runtime cost, blocking patterns, and race-risk signals.", _by_capability(capability, {"performance", "concurrency"})[:8], 0.74),
        AgentReport("analyst", "root cause grouping", _status(ranked), "Grouped findings into root causes and ranked review priority.", ranked[:8], _confidence(ranked, 0.76)),
        AgentReport("challenger", "second-opinion pressure test", _status(classified), "Compared Sergeant findings with external evidence and challenged disagreement.", classified[:8], _confidence(classified, 0.76)),
        AgentReport("archivist", "verified learning memory", "pass" if _safe_dict(learning.get("learning")).get("candidate_count", 0) == 0 else "needs_work", "Prepared verified learning candidates from human outcomes.", _safe_list(_safe_dict(learning.get("learning")).get("candidates"))[:8], 0.82),
        AgentReport("judge", "graduation benchmark", "pass" if graduation.get("verdict") in {"GRADUATED", "TRUSTED_WITH_WATCH"} else "needs_work", "Scored trust benchmark against reference reviewer evidence.", [{"verdict": graduation.get("verdict"), "delta": graduation.get("delta")}], 0.8),
        AgentReport("hermes", "GitHub messenger", "pass", "Prepared app/GitHub-ready summary for delivery.", [{"delivery": "app_bridge", "external_tools_are_witnesses": True}], 0.86),
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
        "rule": "Specialists advise. Sergeant commands the final review.",
    }


def run_squad_review(review_packet: dict[str, Any], evidence_consensus: dict[str, Any], learning: dict[str, Any] | None = None, graduation: dict[str, Any] | None = None) -> dict[str, object]:
    reports = build_squad_reports(review_packet, evidence_consensus, learning, graduation)
    return {"summary": command_summary(reports), "reports": reports}
