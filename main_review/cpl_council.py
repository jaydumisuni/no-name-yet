"""Elastic council helpers for Cpl."""
from __future__ import annotations

import os
import re
from collections import Counter
from typing import Any

from .cpl_reasoning import SPECIALISTS, cpl_depth

CATEGORY_SPECIALIST = {
    "security": "security",
    "architecture": "architecture",
    "api_contract": "tests_contracts",
    "tests": "tests_contracts",
    "documentation": "tests_contracts",
    "correctness": "correctness",
    "concurrency": "performance_concurrency",
    "performance": "performance_concurrency",
    "maintainability": "architecture",
    "other": "correctness",
}


def _bounded_int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return min(high, max(low, value))


def max_rounds() -> int:
    default = {"single": 1, "adaptive": 2, "deep": 3, "maximum": 4}[cpl_depth()]
    return _bounded_int("SERGEANT_CPL_MAX_ROUNDS", default, 1, 6)


def max_members() -> int:
    default = {"single": 1, "adaptive": 5, "deep": 7, "maximum": 9}[cpl_depth()]
    return _bounded_int("SERGEANT_CPL_MAX_COUNCIL_MEMBERS", default, 1, 12)


def available_models(route: Any) -> list[str]:
    output: list[str] = []
    for value in [route.model, *route.discovered_models]:
        model = str(value or "").strip()
        if model and model not in output:
            output.append(model)
    return output


def specialist_for_text(value: object) -> str:
    text = str(value or "").lower()
    if any(word in text for word in ("access", "permission", "credential", "security")):
        return "security"
    if any(word in text for word in ("contract", "test", "proof", "documentation", "workflow")):
        return "tests_contracts"
    if any(word in text for word in ("architecture", "dependency", "lifecycle", "module")):
        return "architecture"
    if any(word in text for word in ("thread", "lock", "async", "race", "performance", "cache", "retry")):
        return "performance_concurrency"
    return "correctness"


def finding_key(finding: dict[str, Any]) -> tuple[object, ...]:
    message = re.sub(r"\W+", " ", str(finding.get("message", "")).lower()).strip()
    return finding.get("path"), finding.get("line_start"), finding.get("line_end"), message


def finding_reference(finding: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": finding.get("path"),
        "line_start": finding.get("line_start"),
        "line_end": finding.get("line_end"),
        "message": finding.get("message"),
        "category": finding.get("category"),
    }


def gap_signature(gap: dict[str, Any]) -> tuple[str, str, str]:
    return str(gap.get("type")), str(gap.get("specialist")), str(gap.get("reason"))


def _resolved_signatures(passes: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    return {
        tuple(str(part) for part in item.get("resolved_gap_signature", []))
        for item in passes
        if item.get("resolution_status") == "answered" and len(item.get("resolved_gap_signature", [])) == 3
    }


def assess(passes: list[dict[str, Any]], plan: list[dict[str, Any]], errors: list[str], model_count: int) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    completed = {str(item.get("specialist")) for item in passes}
    for item in plan:
        specialist = str(item.get("specialist") or "")
        if specialist and specialist not in completed:
            gaps.append({"type": "missing_report", "specialist": specialist, "officer": item.get("officer"), "reason": f"Planned {specialist} report did not complete."})
    for error in errors:
        specialist = specialist_for_text(error)
        gaps.append({"type": "failed_member", "specialist": specialist, "officer": SPECIALISTS[specialist].officer, "reason": str(error)})
    verdicts = {str(item.get("verdict")) for item in passes if item.get("verdict")}
    if len(verdicts) > 1:
        gaps.append({"type": "disagreement", "specialist": "tests_contracts", "officer": "Engineer", "reason": f"Council verdicts disagree: {', '.join(sorted(verdicts))}."})
    for question in sorted({str(q) for item in passes for q in item.get("unanswered_questions", []) if str(q).strip()})[:4]:
        specialist = specialist_for_text(question)
        gaps.append({"type": "unanswered_question", "specialist": specialist, "officer": SPECIALISTS[specialist].officer, "reason": question})
    if model_count > 1:
        support: dict[tuple[object, ...], set[str]] = {}
        for report in passes:
            for finding in report.get("findings", []):
                support.setdefault(finding_key(finding), set()).add(str(report.get("model")))
        for report in passes:
            for finding in report.get("findings", []):
                if finding.get("severity") not in {"blocker", "major"} or len(support.get(finding_key(finding), set())) > 1:
                    continue
                specialist = CATEGORY_SPECIALIST.get(str(finding.get("category") or "other"), "correctness")
                gaps.append({
                    "type": "independent_confirmation",
                    "specialist": specialist,
                    "officer": SPECIALISTS[specialist].officer,
                    "reason": f"High-impact finding has one model source: {finding.get('message')}",
                    "target_finding": finding_reference(finding),
                })

    resolved = _resolved_signatures(passes)
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for gap in gaps:
        signature = gap_signature(gap)
        if signature not in resolved:
            unique.setdefault(signature, gap)
    order = {"failed_member": 0, "missing_report": 1, "recurrence": 2, "disagreement": 3, "unanswered_question": 4, "independent_confirmation": 5}
    return sorted(unique.values(), key=lambda item: (order.get(str(item["type"]), 9), str(item["specialist"]), str(item["reason"])))


def instruction(gap: dict[str, Any], round_number: int) -> dict[str, Any]:
    specialist = str(gap.get("specialist") or "correctness")
    assignment = SPECIALISTS.get(specialist, SPECIALISTS["correctness"])
    return {
        "round": round_number,
        "to_officer": gap.get("officer") or assignment.officer,
        "support_specialist": specialist,
        "instruction": f"Resolve or narrow this tabled gap using current repository evidence: {gap.get('reason')}",
        "required_evidence": ["path and line range", "grounded evidence", "explicit council resolution"],
        "gap_type": gap.get("type"),
        "gap_signature": list(gap_signature(gap)),
        "target_finding": gap.get("target_finding"),
    }


def agreement(passes: list[dict[str, Any]]) -> float:
    verdicts = [str(item.get("verdict")) for item in passes if item.get("verdict")]
    return round(Counter(verdicts).most_common(1)[0][1] / len(verdicts), 3) if verdicts else 0.0
