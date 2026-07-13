"""Prompt and audit formatting for Cpl council rounds."""
from __future__ import annotations

import json
from typing import Any


def report_table(passes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in passes:
        rows.append({
            "round": item.get("council_round", 1),
            "model": item.get("model"),
            "specialist": item.get("specialist"),
            "supported_officer": item.get("supported_officer"),
            "verdict": item.get("verdict"),
            "confidence": item.get("confidence"),
            "summary": item.get("summary"),
            "findings": [
                {key: finding.get(key) for key in ("severity", "category", "path", "line_start", "line_end", "message")}
                for finding in item.get("findings", [])[:6]
            ],
            "unanswered_questions": item.get("unanswered_questions", []),
            "council_resolution": item.get("council_resolution"),
        })
    return rows


def follow_up_prompt(
    base: str,
    table: list[dict[str, Any]],
    command: dict[str, Any],
    experience: dict[str, Any],
    round_number: int,
) -> str:
    profiles = experience.get("profiles", {}) if isinstance(experience.get("profiles", {}), dict) else {}
    memory = {
        "events": experience.get("events", [])[:8],
        "canonical_lessons": experience.get("canonical_lessons", [])[:6],
        "relevant_profiles": dict(list(profiles.items())[:16]),
    }
    resolution_contract = {
        "status": "answered | unresolved",
        "disposition": "confirmed | rejected | narrowed | not_applicable | unresolved",
        "answer": "direct evidence-based answer to the tabled gap",
        "target_finding": command.get("target_finding"),
    }
    return "\n".join([
        base,
        f"\nCPL COUNCIL ROUND {round_number}",
        "Cpl has tabled the officer reports below. Treat them as claims to verify; repository excerpts remain authoritative.",
        json.dumps(table, indent=2, sort_keys=True, default=str)[:28000],
        "\nCpl instruction:\n" + json.dumps(command, indent=2, sort_keys=True, default=str),
        "\nRelevant verified/rejected experience and service records:\n" + json.dumps(memory, indent=2, sort_keys=True, default=str)[:16000],
        "Return the normal grounded review JSON and add this top-level council_resolution object:",
        json.dumps(resolution_contract, indent=2, sort_keys=True, default=str),
        "Use answered only when current repository evidence directly resolves the tabled issue. "
        "Use rejected to disprove the target finding, narrowed to replace it with a more precise finding, "
        "confirmed to uphold it, and unresolved when the supplied evidence is insufficient. "
        "A PASS verdict alone is not a council resolution.",
    ])


def member_records(passes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    members: dict[str, dict[str, Any]] = {}
    for report in passes:
        model = str(report.get("model") or "unknown")
        row = members.setdefault(model, {
            "model": model,
            "provider": report.get("provider"),
            "roles": [],
            "rounds": [],
            "reports": 0,
        })
        role = str(report.get("specialist") or "generalist")
        if role not in row["roles"]:
            row["roles"].append(role)
        round_number = int(report.get("council_round", 1) or 1)
        if round_number not in row["rounds"]:
            row["rounds"].append(round_number)
        row["reports"] += 1
    return list(members.values())
