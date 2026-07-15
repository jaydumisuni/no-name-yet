"""Cross-source Cpl finding reconciliation and noise governance.

Cpl keeps every grounded report in its audit packet, but only novel, sufficiently
supported defects should become additional Sergeant actions. Deterministic
findings remain authoritative and model confirmations should strengthen them
without being counted as new defects.
"""
from __future__ import annotations

from typing import Any

from .cpl_council import finding_root_cause, findings_match

SEVERITY_RANK = {"note": 0, "minor": 1, "major": 2, "blocker": 3}


def _path(finding: dict[str, Any]) -> str:
    return str(finding.get("path") or "").replace("\\", "/")


def _lines(finding: dict[str, Any]) -> tuple[int | None, int | None]:
    try:
        start = int(finding.get("line_start") or finding.get("line"))
    except (TypeError, ValueError):
        return None, None
    try:
        end = int(finding.get("line_end") or start)
    except (TypeError, ValueError):
        end = start
    return max(1, start), max(start, end)


def _line_distance(left: dict[str, Any], right: dict[str, Any]) -> int | None:
    left_start, left_end = _lines(left)
    right_start, right_end = _lines(right)
    if None in {left_start, left_end, right_start, right_end}:
        return None
    assert left_start is not None and left_end is not None
    assert right_start is not None and right_end is not None
    if left_end >= right_start and right_end >= left_start:
        return 0
    return max(right_start - left_end, left_start - right_end)


def finding_family(finding: dict[str, Any]) -> str:
    """Return a broad action family suitable for cross-source reconciliation."""

    category = str(finding.get("category") or finding.get("capability") or "other").strip().lower()
    root = finding_root_cause(finding)
    if root in {"unsafe-shell-execution", "sql-injection", "unsafe-data-flow"}:
        return "unsafe-data-flow"
    if root in {
        "unsafe-file-access",
        "authorization-gap",
        "secret-exposure",
        "architecture-boundary",
        "proof-gap",
        "change-impact",
    }:
        return root
    if root == "runtime-risk":
        return f"runtime-risk:{category}"
    if root:
        return root
    if category in {"data_flow", "security_taint"}:
        return "unsafe-data-flow"
    if category == "architecture":
        return "architecture-boundary"
    if category in {"concurrency", "performance"}:
        return f"runtime-risk:{category}"
    if category == "api_contract":
        return "change-impact"
    if category in {"tests", "test_impact", "documentation"}:
        return "proof-gap"
    return category


def findings_overlap(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    max_line_distance: int = 10,
) -> bool:
    """Return whether two sources describe the same actionable defect family."""

    if findings_match(left, right, max_line_distance=max_line_distance):
        return True
    left_path = _path(left)
    right_path = _path(right)
    if not left_path or left_path != right_path:
        return False
    distance = _line_distance(left, right)
    if distance is None or distance > max_line_distance:
        return False
    left_family = finding_family(left)
    right_family = finding_family(right)
    return bool(left_family and left_family == right_family)


def _reference(finding: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": finding.get("path"),
        "line_start": finding.get("line_start"),
        "line_end": finding.get("line_end"),
        "category": finding.get("category") or finding.get("capability"),
        "severity": finding.get("severity"),
        "message": finding.get("message"),
        "root_cause": finding.get("root_cause") or finding_root_cause(finding) or None,
    }


def _supporting_models(finding: dict[str, Any]) -> list[str]:
    values = finding.get("supporting_models", [])
    if not isinstance(values, list):
        return []
    return sorted({str(value) for value in values if value is not None and str(value).strip()})


def _decision_verdict(
    actionable: list[dict[str, Any]],
    unconfirmed: list[dict[str, Any]],
) -> str:
    rows = [*actionable, *unconfirmed]
    if any(str(item.get("severity")) == "blocker" for item in actionable):
        return "BLOCK"
    if any(str(item.get("severity")) in {"blocker", "major"} for item in rows):
        return "NEEDS WORK"
    return "PASS"


def reconcile_cpl_findings(
    cpl: dict[str, Any],
    deterministic_findings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Classify Cpl findings as confirmations, advisories, or novel actions.

    Raw Cpl findings remain available for audit. ``actionable_findings`` is the
    noise-governed surface consumed by Sergeant actions and blind quality proof.
    """

    output = dict(cpl)
    deterministic = [dict(item) for item in deterministic_findings if isinstance(item, dict)]
    confirmed: list[dict[str, Any]] = []
    advisory: list[dict[str, Any]] = []
    unconfirmed: list[dict[str, Any]] = []
    actionable: list[dict[str, Any]] = []

    for raw in cpl.get("findings", []):
        if not isinstance(raw, dict):
            continue
        finding = dict(raw)
        family = finding_family(finding)
        if family and not finding.get("root_cause"):
            finding["root_cause"] = family
        overlaps = [item for item in deterministic if findings_overlap(finding, item)]
        if overlaps:
            finding["classification"] = "deterministic_confirmation"
            finding["confirmed_against"] = [_reference(item) for item in overlaps]
            confirmed.append(finding)
            continue

        severity = str(finding.get("severity") or "note").lower()
        supporters = _supporting_models(finding)
        finding["supporting_models"] = supporters
        if severity in {"note", "minor"}:
            finding["classification"] = "advisory"
            advisory.append(finding)
            continue

        evidence_verified = finding.get("evidence_verified") is True
        independently_supported = len(supporters) >= 2
        if evidence_verified and (severity == "blocker" or independently_supported):
            finding["classification"] = "novel_actionable"
            actionable.append(finding)
        else:
            finding["classification"] = "novel_unconfirmed"
            unconfirmed.append(finding)

    output.update(
        {
            "actionable_findings": actionable,
            "confirmed_findings": confirmed,
            "advisory_findings": advisory,
            "unconfirmed_findings": unconfirmed,
            "decision_findings": [*actionable, *unconfirmed],
            "decision_verdict": _decision_verdict(actionable, unconfirmed),
            "noise_governor": {
                "raw_count": len([item for item in cpl.get("findings", []) if isinstance(item, dict)]),
                "actionable_count": len(actionable),
                "confirmation_count": len(confirmed),
                "advisory_count": len(advisory),
                "unconfirmed_count": len(unconfirmed),
                "rule": (
                    "Deterministic confirmations strengthen existing evidence; model-only minor findings remain "
                    "advisory; novel major findings require independent support; verified blockers remain actionable."
                ),
            },
        }
    )
    return output
