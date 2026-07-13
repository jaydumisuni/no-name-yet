"""Policy normalization for Tier 1 capability findings.

Call-graph and cross-file findings describe blast radius. They are important
review signals, but dependency existence alone is not a demonstrated defect and
must not block a merge when no contract, regression, security, or test-impact
evidence accompanies it.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

IMPACT_ONLY_CAPABILITIES = {"call_graph", "cross_file"}


def normalize_capability_review(packet: dict[str, Any]) -> dict[str, Any]:
    """Return a capability packet with impact-only severities capped at minor."""

    normalized = deepcopy(packet)
    raw_findings = normalized.get("findings", [])
    findings = raw_findings if isinstance(raw_findings, list) else []
    adjustments: list[dict[str, object]] = []

    for finding in findings:
        if not isinstance(finding, dict):
            continue
        capability = str(finding.get("capability", ""))
        severity = str(finding.get("severity", ""))
        if capability in IMPACT_ONLY_CAPABILITIES and severity in {"blocker", "major"}:
            adjustments.append(
                {
                    "capability": capability,
                    "path": finding.get("path"),
                    "from": severity,
                    "to": "minor",
                    "reason": "Dependency or caller presence is blast-radius evidence, not a demonstrated defect.",
                }
            )
            finding["severity"] = "minor"
            finding["impact_signal"] = True

    blockers = [item for item in findings if isinstance(item, dict) and item.get("severity") == "blocker"]
    majors = [item for item in findings if isinstance(item, dict) and item.get("severity") == "major"]
    normalized["verdict"] = "BLOCK" if blockers else "NEEDS WORK" if majors else "PASS"
    normalized["policy_adjustments"] = adjustments
    return normalized
