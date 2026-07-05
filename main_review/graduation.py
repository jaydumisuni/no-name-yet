"""Tier 5 graduation benchmark for Sergeant.

Tier 5 is not a claim that Sergeant is perfect. It is a repeatable scorecard
for deciding whether Sergeant is trusted enough on real review work.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

WEIGHTS = {
    "real_bugs_found": 25,
    "false_positive_control": 20,
    "explanation_quality": 15,
    "architecture_reasoning": 15,
    "security_findings": 10,
    "regression_prediction": 10,
    "documentation_consistency": 5,
}

@dataclass(frozen=True)
class BenchmarkResult:
    reviewer: str
    score: float
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _score_metrics(metrics: dict[str, Any]) -> float:
    total = 0.0
    for name, weight in WEIGHTS.items():
        value = max(0.0, min(1.0, _number(metrics.get(name))))
        total += value * weight
    return round(total / 10, 2)


def _result(name: str, metrics: dict[str, Any], strengths: list[str] | None = None, weaknesses: list[str] | None = None) -> BenchmarkResult:
    return BenchmarkResult(
        reviewer=name,
        score=_score_metrics(metrics),
        strengths=strengths or [],
        weaknesses=weaknesses or [],
        metrics={key: max(0.0, min(1.0, _number(metrics.get(key)))) for key in WEIGHTS},
    )


def run_graduation_benchmark(sergeant: dict[str, Any], reference: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compare Sergeant against an optional reference reviewer using a fixed scorecard."""
    reference = reference or {"name": "Reference", "metrics": {}}
    sergeant_result = _result(
        str(sergeant.get("name") or "Sergeant"),
        sergeant.get("metrics", {}),
        list(sergeant.get("strengths", [])),
        list(sergeant.get("weaknesses", [])),
    )
    reference_result = _result(
        str(reference.get("name") or "Reference"),
        reference.get("metrics", {}),
        list(reference.get("strengths", [])),
        list(reference.get("weaknesses", [])),
    )
    delta = round(sergeant_result.score - reference_result.score, 2)
    graduated = sergeant_result.score >= 8.5 and delta >= 0
    if graduated:
        verdict = "GRADUATED"
    elif sergeant_result.score >= 8.0:
        verdict = "TRUSTED_WITH_WATCH"
    else:
        verdict = "NEEDS_MORE_PROOF"
    gaps = []
    for metric in WEIGHTS:
        s_value = sergeant_result.metrics.get(metric, 0.0)
        r_value = reference_result.metrics.get(metric, 0.0)
        if s_value < r_value:
            gaps.append({"metric": metric, "sergeant": s_value, "reference": r_value, "gap": round(r_value - s_value, 2)})
    return {
        "verdict": verdict,
        "graduated": graduated,
        "delta": delta,
        "scorecard": WEIGHTS,
        "sergeant": sergeant_result.to_dict(),
        "reference": reference_result.to_dict(),
        "gaps": gaps,
        "rule": "Sergeant graduates by earned evidence across real reviews, not by feature claims.",
    }


def summarize_graduation(packet: dict[str, Any]) -> str:
    lines = [
        "# Sergeant Graduation Benchmark",
        "",
        f"Verdict: **{packet.get('verdict')}**",
        f"Graduated: **{packet.get('graduated')}**",
        f"Delta: **{packet.get('delta')}**",
        "",
        "## Scores",
        f"- Sergeant: {packet.get('sergeant', {}).get('score')}",
        f"- Reference: {packet.get('reference', {}).get('score')}",
    ]
    gaps = packet.get("gaps", [])
    if gaps:
        lines.extend(["", "## Capability gaps"])
        for gap in gaps:
            lines.append(f"- {gap['metric']}: Sergeant {gap['sergeant']} vs reference {gap['reference']}")
    lines.extend(["", "## Rule", str(packet.get("rule"))])
    return "\n".join(lines) + "\n"
