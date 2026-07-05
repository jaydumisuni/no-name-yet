"""Tier 2 review intelligence for Sergeant."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SEVERITY_POINTS = {"blocker": 100, "major": 75, "minor": 40, "note": 15}
CAPABILITY_POINTS = {
    "security_taint": 18,
    "data_flow": 16,
    "api_contract": 14,
    "regression": 13,
    "cross_file": 12,
    "concurrency": 12,
    "architecture": 10,
    "test_impact": 9,
    "performance": 8,
    "call_graph": 7,
}

@dataclass(frozen=True)
class RankedFinding:
    capability: str
    severity: str
    message: str
    evidence: str
    confidence: float
    priority: int
    root_cause: str
    why_it_matters: str
    safer_alternative: str
    challenge_result: str
    path: str | None = None
    related_paths: list[str] = field(default_factory=list)
    duplicate_count: int = 1

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

def _text(value: object) -> str:
    return str(value or "").strip()

def _key(finding: dict[str, Any]) -> tuple[str, str, str | None]:
    return (_text(finding.get("capability")), _text(finding.get("message")).lower(), finding.get("path"))

def _root(finding: dict[str, Any]) -> str:
    cap = _text(finding.get("capability"))
    if cap in {"security_taint", "data_flow"}:
        return "unsafe-data-flow"
    if cap in {"api_contract", "cross_file", "call_graph", "regression"}:
        return "change-impact"
    if cap == "test_impact":
        return "proof-gap"
    if cap in {"performance", "concurrency"}:
        return "runtime-risk"
    if cap == "architecture":
        return "architecture-boundary"
    return cap or "general-review"

def _confidence(finding: dict[str, Any], duplicate_count: int) -> float:
    score = float(finding.get("confidence") or 0.5)
    if _text(finding.get("evidence")):
        score += 0.08
    if finding.get("related_paths"):
        score += 0.04
    if duplicate_count > 1:
        score += min(0.08, duplicate_count * 0.02)
    return round(max(0.1, min(0.99, score)), 2)

def _priority(finding: dict[str, Any], confidence: float) -> int:
    return int(SEVERITY_POINTS.get(_text(finding.get("severity")), 25) + CAPABILITY_POINTS.get(_text(finding.get("capability")), 5) + confidence * 10)

def _why(capability: str) -> str:
    return {
        "security_taint": "Untrusted data near sensitive logic can create safety, integrity, or abuse risk.",
        "data_flow": "Unsafe data movement can turn a small local change into a wider system defect.",
        "api_contract": "Contract drift can break callers even when local tests pass.",
        "regression": "A high blast-radius change can break dependent behavior.",
        "cross_file": "Dependent files mean the real risk is wider than the edited file.",
        "test_impact": "Changed behavior without matching proof raises regression risk.",
        "architecture": "Boundary drift makes future changes harder and hides coupling.",
        "performance": "Small local cost can become production cost under load.",
        "concurrency": "Timing-dependent bugs are hard to reproduce after release.",
    }.get(capability, "This finding affects review confidence and should be checked before merge.")

def _alternative(capability: str) -> str:
    return {
        "security_taint": "Validate inputs and use safe wrapper APIs before sensitive operations.",
        "data_flow": "Keep untrusted values away from unsafe sinks or add explicit sanitizing.",
        "api_contract": "Add a contract test or document the compatibility decision.",
        "regression": "Run or add tests around the dependent modules.",
        "cross_file": "Review dependent files and add focused coverage for the changed path.",
        "test_impact": "Add a focused test or document why existing proof is enough.",
        "architecture": "Move the dependency behind the existing boundary or add an ADR.",
        "performance": "Prefer batching, caching, streaming, or simpler data structures.",
        "concurrency": "Use request-scoped state, locks, queues, or immutable data.",
    }.get(capability, "Add evidence that the change is intentional and covered.")

def _challenge(finding: dict[str, Any]) -> str:
    if not _text(finding.get("evidence")):
        return "weakened: missing direct evidence"
    if float(finding.get("confidence") or 0.0) < 0.55:
        return "weakened: low confidence"
    return "survived: enough evidence for review output"

def run_review_intelligence(review_packet: dict[str, Any]) -> dict[str, Any]:
    capability_review = review_packet.get("capability_review", {}) if isinstance(review_packet, dict) else {}
    raw = capability_review.get("findings", []) if isinstance(capability_review, dict) else []
    groups: dict[tuple[str, str, str | None], list[dict[str, Any]]] = {}
    for item in raw:
        if isinstance(item, dict):
            groups.setdefault(_key(item), []).append(item)

    ranked: list[RankedFinding] = []
    roots: dict[str, list[str]] = {}
    for duplicates in groups.values():
        item = duplicates[0]
        cap = _text(item.get("capability"))
        conf = _confidence(item, len(duplicates))
        root = _root(item)
        roots.setdefault(root, []).append(_text(item.get("message")))
        ranked.append(RankedFinding(
            capability=cap,
            severity=_text(item.get("severity")),
            message=_text(item.get("message")),
            evidence=_text(item.get("evidence")),
            confidence=conf,
            priority=_priority(item, conf),
            root_cause=root,
            why_it_matters=_why(cap),
            safer_alternative=_alternative(cap),
            challenge_result=_challenge(item),
            path=item.get("path"),
            related_paths=list(item.get("related_paths") or []),
            duplicate_count=len(duplicates),
        ))
    ranked.sort(key=lambda finding: finding.priority, reverse=True)
    blockers = [finding for finding in ranked if finding.severity == "blocker"]
    majors = [finding for finding in ranked if finding.severity == "major"]
    verdict = "BLOCK" if blockers else "NEEDS WORK" if majors else "PASS"
    quality_score = max(0, min(100, 100 - min(35, len(majors) * 7) - min(25, len(blockers) * 15) + min(10, len(roots) * 2)))
    return {
        "verdict": verdict,
        "quality_score": quality_score,
        "finding_count": len(ranked),
        "root_causes": {key: sorted(set(values)) for key, values in roots.items()},
        "ranked_findings": [finding.to_dict() for finding in ranked],
        "trace": [
            "Collected Tier 1 findings.",
            f"Consolidated {len(raw)} raw finding(s) into {len(ranked)} ranked finding(s).",
            f"Grouped findings into {len(roots)} root cause bucket(s).",
            f"Final Tier 2 verdict: {verdict}.",
        ],
    }
