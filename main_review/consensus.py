"""Multi-reviewer consensus for Main Review."""

from __future__ import annotations

from typing import Any


def build_consensus(reviewer_outputs: list[dict[str, Any]]) -> dict[str, Any]:
    signals: list[dict[str, object]] = []
    for output in reviewer_outputs:
        source = str(output.get("source", "reviewer"))
        verdict = str(output.get("verdict", output.get("decision", "unknown")))
        evidence = output.get("evidence", [])
        signals.append(
            {
                "source": source,
                "verdict": verdict,
                "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
                "weight": 2 if source in {"main-review", "hunter", "human"} else 1,
            }
        )

    blocking = [signal for signal in signals if signal["verdict"] in {"BLOCK", "REQUEST_CHANGES", "fix"}]
    needs_work = [signal for signal in signals if signal["verdict"] in {"NEEDS WORK", "consider"}]
    pass_like = [signal for signal in signals if signal["verdict"] in {"PASS", "approve"}]

    if blocking:
        consensus = "BLOCK"
    elif needs_work:
        consensus = "NEEDS WORK"
    elif pass_like:
        consensus = "PASS"
    else:
        consensus = "NO CONSENSUS"

    return {
        "consensus": consensus,
        "signals": signals,
        "summary": {
            "total_sources": len(signals),
            "blocking": len(blocking),
            "needs_work": len(needs_work),
            "pass_like": len(pass_like),
        },
        "rule": "Evidence beats vote count; blocking evidence wins until answered.",
    }
