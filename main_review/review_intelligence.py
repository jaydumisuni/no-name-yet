"""Tier 2 review intelligence for Sergeant.

Tier 1 scanners deliberately over-collect signals. Tier 2 consolidates,
challenges, explains, and promotes only evidence-bearing findings. Its quality
score measures the completeness of the finding-specific review output, never
the quality of the code under review.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from statistics import mean
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
_PATH_OPTIONAL = {"test_impact"}
_GENERIC_EVIDENCE_PHRASES = (
    "patterns were both detected",
    "needs validation review",
    "requires compatibility review",
    "may create scaling risk",
    "may need race-condition review",
    "path name indicates",
    "appears near a risky sink",
)
_EVIDENCE_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.I)


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
    trigger: str
    consequence: str
    safer_alternative: str
    verification_test: str
    challenge_result: str
    evidence_strength: float
    completeness_score: float
    path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    related_paths: list[str] = field(default_factory=list)
    duplicate_count: int = 1
    promoted: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _text(value: object) -> str:
    return str(value or "").strip()


def _key(finding: dict[str, Any]) -> tuple[str, str, str | None, int | None]:
    return (
        _text(finding.get("capability")),
        _text(finding.get("message")).lower(),
        finding.get("path"),
        finding.get("line_start") or finding.get("line"),
    )


def _root(finding: dict[str, Any]) -> str:
    explicit = _text(finding.get("root_cause"))
    if explicit:
        return explicit
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
    raw = finding.get("confidence")
    score = float(raw) if raw is not None else 0.5
    if _text(finding.get("evidence")):
        score += 0.08
    if finding.get("related_paths"):
        score += 0.04
    if duplicate_count > 1:
        score += min(0.08, duplicate_count * 0.02)
    return round(max(0.0, min(0.99, score)), 2)


def _priority(finding: dict[str, Any], confidence: float) -> int:
    return int(
        SEVERITY_POINTS.get(_text(finding.get("severity")), 25)
        + CAPABILITY_POINTS.get(_text(finding.get("capability")), 5)
        + confidence * 10
    )


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
        "call_graph": "Changed exported behavior can affect callers outside the edited file.",
    }.get(capability, "This finding affects review confidence and should be checked before merge.")


def _trigger(capability: str) -> str:
    return {
        "security_taint": "A caller supplies untrusted input that reaches security-sensitive logic.",
        "data_flow": "The changed path accepts external input and carries it into a risky sink.",
        "api_contract": "An existing or new caller uses the changed route, schema, or public interface.",
        "regression": "A dependent module executes behavior supplied by the changed file.",
        "cross_file": "A dependent import or caller exercises the changed module.",
        "test_impact": "The changed behavior is merged without focused regression proof.",
        "architecture": "The changed module crosses an established layer or ownership boundary.",
        "performance": "The changed loop or mapping path receives production-scale input.",
        "concurrency": "Two tasks or requests access the shared mutable state at the same time.",
        "call_graph": "A downstream caller invokes the changed exported symbol.",
    }.get(capability, "The affected path is exercised under the conditions described by the evidence.")


def _consequence(capability: str) -> str:
    return {
        "security_taint": "The system may expose data, execute unintended operations, or accept malicious input.",
        "data_flow": "A local input-handling defect may propagate into stored data or downstream behavior.",
        "api_contract": "Clients may fail, silently misbehave, or require an undocumented migration.",
        "regression": "Previously working dependent behavior may break after the change.",
        "cross_file": "The true impact may extend beyond the edited file.",
        "test_impact": "A regression may reach users without a failing proof gate.",
        "architecture": "Coupling and ownership drift can make later changes unsafe or harder to reason about.",
        "performance": "Latency, CPU, or memory cost may grow non-linearly.",
        "concurrency": "Results may be lost, duplicated, corrupted, or timing-dependent.",
        "call_graph": "Callers may observe incompatible or unintended behavior.",
    }.get(capability, "The issue may reduce confidence in the change or its surrounding system.")


def _alternative(capability: str) -> str:
    return {
        "security_taint": "Validate inputs and use safe wrapper APIs before sensitive operations.",
        "data_flow": "Keep untrusted values away from unsafe sinks or add explicit sanitizing.",
        "api_contract": "Preserve compatibility or document and test the migration contract.",
        "regression": "Review dependent modules and add focused coverage for the affected behavior.",
        "cross_file": "Review dependent files and keep the change behind the existing boundary.",
        "test_impact": "Add a focused test or document why existing proof is sufficient.",
        "architecture": "Move the dependency behind the existing boundary or add an approved architecture decision.",
        "performance": "Prefer batching, caching, streaming, indexing, or a lower-complexity algorithm.",
        "concurrency": "Use request-scoped state, locks, queues, transactions, or immutable data.",
        "call_graph": "Preserve the exported contract or update and test every affected caller.",
    }.get(capability, "Add evidence that the change is intentional and covered.")


def _verification(capability: str) -> str:
    return {
        "security_taint": "Add a negative test with malicious or malformed input and prove the sensitive sink remains safe.",
        "data_flow": "Add an end-to-end test that traces representative untrusted input through the changed path.",
        "api_contract": "Add a contract test for existing callers and any intended migration behavior.",
        "regression": "Run or add focused tests for the named dependent modules and rollback path.",
        "cross_file": "Add tests that exercise the changed module through at least one real dependent caller.",
        "test_impact": "Add a focused regression test that fails before the fix and passes after it.",
        "architecture": "Add an import/boundary test or architecture rule that prevents the forbidden dependency.",
        "performance": "Add a representative benchmark with an explicit acceptable threshold.",
        "concurrency": "Add a repeated parallel test that proves updates are not lost or duplicated.",
        "call_graph": "Add a caller-level regression test for every affected exported behavior.",
    }.get(capability, "Add a focused test that reproduces the risk and proves the intended behavior.")


def _evidence_strength(finding: dict[str, Any], confidence: float) -> float:
    score = confidence * 0.55
    if _text(finding.get("evidence")):
        score += 0.2
    if finding.get("path"):
        score += 0.12
    if finding.get("line_start") or finding.get("line"):
        score += 0.08
    if finding.get("related_paths"):
        score += 0.05
    return round(min(1.0, score), 2)


def _evidence_is_specific(finding: dict[str, Any]) -> bool:
    evidence = _text(finding.get("evidence"))
    lowered = evidence.lower()
    if not evidence:
        return False
    tokens = {token.lower() for token in _EVIDENCE_TOKEN_RE.findall(evidence) if len(token) > 2}
    has_location = bool(finding.get("line_start") or finding.get("line") or finding.get("evidence_ref"))
    has_related_scope = bool(finding.get("related_paths"))
    has_concrete_marker = bool(re.search(r"[()/:?=._-]|\b\d+\b", evidence))
    generic_only = any(phrase in lowered for phrase in _GENERIC_EVIDENCE_PHRASES) and not has_concrete_marker
    if generic_only:
        return False
    if _text(finding.get("capability")) in _PATH_OPTIONAL:
        return len(tokens) >= 6 and (has_concrete_marker or has_related_scope)
    return len(tokens) >= 6 and (has_location or has_related_scope or has_concrete_marker)


def _challenge(finding: dict[str, Any], evidence_strength: float) -> str:
    capability = _text(finding.get("capability"))
    if not _text(finding.get("evidence")):
        return "weakened: missing direct evidence"
    if capability not in _PATH_OPTIONAL and not finding.get("path"):
        return "weakened: missing affected path"
    raw_confidence = finding.get("confidence")
    confidence = float(raw_confidence) if raw_confidence is not None else 0.5
    if confidence < 0.55:
        return "weakened: low confidence"
    if not _evidence_is_specific(finding):
        return "weakened: evidence is too generic"
    if evidence_strength < 0.65:
        return "weakened: evidence strength is below the promotion threshold"
    return "survived: evidence is specific enough for review output"


def _completeness(finding: dict[str, Any], capability: str, evidence_strength: float) -> float:
    path_present = bool(finding.get("path")) or capability in _PATH_OPTIONAL
    location_present = bool(finding.get("line_start") or finding.get("line") or finding.get("evidence_ref")) or capability in _PATH_OPTIONAL
    direct_evidence = bool(finding.get("direct_evidence")) or capability in _PATH_OPTIONAL
    checks = [
        bool(_text(finding.get("message"))),
        bool(_text(finding.get("evidence"))),
        path_present,
        location_present,
        bool(_text(finding.get("root_cause"))) or bool(capability),
        finding.get("confidence") is not None,
        direct_evidence,
    ]
    return round((sum(checks) / len(checks)) * 0.8 + evidence_strength * 0.2, 2)


def run_review_intelligence(review_packet: dict[str, Any]) -> dict[str, Any]:
    capability_review = review_packet.get("capability_review", {}) if isinstance(review_packet, dict) else {}
    raw = capability_review.get("findings", []) if isinstance(capability_review, dict) else []
    groups: dict[tuple[str, str, str | None, int | None], list[dict[str, Any]]] = {}
    for item in raw:
        if isinstance(item, dict):
            groups.setdefault(_key(item), []).append(item)

    ranked: list[RankedFinding] = []
    roots: dict[str, list[str]] = {}
    for duplicates in groups.values():
        item = duplicates[0]
        capability = _text(item.get("capability"))
        confidence = _confidence(item, len(duplicates))
        evidence_strength = _evidence_strength(item, confidence)
        challenge = _challenge(item, evidence_strength)
        root = _root(item)
        roots.setdefault(root, []).append(_text(item.get("message")))
        severity = _text(item.get("severity"))
        promoted = severity in {"blocker", "major"} and challenge.startswith("survived:")
        ranked.append(
            RankedFinding(
                capability=capability,
                severity=severity,
                message=_text(item.get("message")),
                evidence=_text(item.get("evidence")),
                confidence=confidence,
                priority=_priority(item, confidence),
                root_cause=root,
                why_it_matters=_why(capability),
                trigger=_trigger(capability),
                consequence=_consequence(capability),
                safer_alternative=_alternative(capability),
                verification_test=_verification(capability),
                challenge_result=challenge,
                evidence_strength=evidence_strength,
                completeness_score=_completeness(item, capability, evidence_strength),
                path=item.get("path"),
                line_start=item.get("line_start") or item.get("line"),
                line_end=item.get("line_end") or item.get("line_start") or item.get("line"),
                related_paths=list(item.get("related_paths") or []),
                duplicate_count=len(duplicates),
                promoted=promoted,
            )
        )

    ranked.sort(key=lambda finding: finding.priority, reverse=True)
    promoted = [finding for finding in ranked if finding.promoted]
    blockers = [finding for finding in promoted if finding.severity == "blocker"]
    majors = [finding for finding in promoted if finding.severity == "major"]
    verdict = "BLOCK" if blockers else "NEEDS WORK" if majors else "PASS"
    quality_score = None if not ranked else round(mean(item.completeness_score for item in ranked) * 100)
    duplicate_total = sum(max(0, item.duplicate_count - 1) for item in ranked)
    duplicate_rate = round(duplicate_total / max(1, len(raw)), 3)
    return {
        "verdict": verdict,
        "quality_score": quality_score,
        "quality_score_kind": "review-output-completeness",
        "quality_score_evaluable": bool(ranked),
        "finding_count": len(ranked),
        "promoted_count": len(promoted),
        "suppressed_count": len(ranked) - len(promoted),
        "duplicate_rate": duplicate_rate,
        "root_causes": {key: sorted(set(values)) for key, values in roots.items()},
        "ranked_findings": [finding.to_dict() for finding in ranked],
        "promoted_findings": [finding.to_dict() for finding in promoted],
        "trace": [
            "Collected Tier 1 findings.",
            f"Consolidated {len(raw)} raw finding(s) into {len(ranked)} ranked finding(s).",
            f"Promoted {len(promoted)} blocker/major finding(s) that survived evidence challenge.",
            f"Suppressed {len(ranked) - len(promoted)} signal(s) from the gate while preserving them for context.",
            f"Grouped findings into {len(roots)} root cause bucket(s).",
            f"Final Tier 2 verdict: {verdict}.",
        ],
    }
