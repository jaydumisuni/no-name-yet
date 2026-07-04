"""Verdict engine for Main Review.

The verdict engine converts normalized evidence into the reviewer's first
machine decision: PASS, NEEDS WORK, or BLOCK. It does not edit files and it does
not execute project code.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from .evidence import collect_evidence

Verdict = Literal["PASS", "NEEDS WORK", "BLOCK"]

SEVERITY_ORDER = {
    "blocker": 4,
    "major": 3,
    "minor": 2,
    "note": 1,
}


@dataclass(frozen=True)
class VerdictReport:
    verdict: Verdict
    reason: str
    blocking_findings: list[dict[str, object]] = field(default_factory=list)
    major_findings: list[dict[str, object]] = field(default_factory=list)
    minor_findings: list[dict[str, object]] = field(default_factory=list)
    notes: list[dict[str, object]] = field(default_factory=list)
    suggested_next_action: str = ""
    finding_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def decide_verdict(evidence_payload: dict[str, object]) -> VerdictReport:
    findings = list(evidence_payload.get("findings", []))
    blocking = [finding for finding in findings if finding.get("severity") == "blocker"]
    major = [finding for finding in findings if finding.get("severity") == "major"]
    minor = [finding for finding in findings if finding.get("severity") == "minor"]
    notes = [finding for finding in findings if finding.get("severity") == "note"]

    if blocking:
        return VerdictReport(
            verdict="BLOCK",
            reason="Blocking evidence was found. This change or repository state must not be accepted until blockers are resolved.",
            blocking_findings=blocking,
            major_findings=major,
            minor_findings=minor,
            notes=notes,
            suggested_next_action="Fix blocker findings first, then rerun review.",
            finding_count=len(findings),
        )

    if major:
        return VerdictReport(
            verdict="NEEDS WORK",
            reason="Major evidence was found. The direction may be acceptable, but it does not clear the standard yet.",
            blocking_findings=blocking,
            major_findings=major,
            minor_findings=minor,
            notes=notes,
            suggested_next_action="Resolve major findings or document why they are intentionally accepted.",
            finding_count=len(findings),
        )

    if minor:
        return VerdictReport(
            verdict="PASS",
            reason="No blockers or major issues were found. Minor findings can be handled without blocking acceptance.",
            blocking_findings=blocking,
            major_findings=major,
            minor_findings=minor,
            notes=notes,
            suggested_next_action="Review minor findings when practical.",
            finding_count=len(findings),
        )

    return VerdictReport(
        verdict="PASS",
        reason="No blocking, major, or minor findings were found.",
        notes=notes,
        suggested_next_action="No action required.",
        finding_count=len(findings),
    )


def review_repository(root: str | Path) -> dict[str, object]:
    evidence_payload = collect_evidence(root)
    report = decide_verdict(evidence_payload)
    return {
        "verdict": report.to_dict(),
        "evidence": evidence_payload,
    }
