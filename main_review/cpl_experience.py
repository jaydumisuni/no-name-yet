"""Governed Cpl, officer, model, and weapon experience records.

The canonical lesson store remains ``memory.json``. This module adds an
append-only operational ledger so Cpl and the permanent officers can retrieve
verified battle experience without treating raw model opinions as doctrine.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .memory import ReviewMemoryStore, default_memory_path

EXPERIENCE_PATH = Path(".main-review/cpl-experience.jsonl")
VALID_STATUSES = {"verified", "rejected", "superseded"}

OFFICER_BY_CATEGORY = {
    "correctness": "Engineer",
    "architecture": "Engineer",
    "api_contract": "Engineer",
    "tests": "Engineer",
    "documentation": "Analyst",
    "security": "Medic",
    "concurrency": "Mechanic",
    "performance": "Mechanic",
    "maintainability": "Engineer",
    "other": "Analyst",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(value: object) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", str(value or ""))
        if token.lower() not in {"the", "and", "for", "with", "from", "this", "that"}
    }


def _stable_id(*parts: object) -> str:
    payload = "\x1f".join(str(part or "") for part in parts)
    return "EXP-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16].upper()


def _ledger_path(root: str | Path) -> Path:
    return Path(root) / EXPERIENCE_PATH


def load_experience_events(root: str | Path) -> list[dict[str, Any]]:
    path = _ledger_path(root)
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("status") in VALID_STATUSES:
            events.append(item)
    return events


def append_experience_events(root: str | Path, events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    path = _ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    known = {str(item.get("event_id")) for item in load_experience_events(root)}
    added: list[dict[str, Any]] = []
    for raw in events:
        item = dict(raw)
        event_id = str(item.get("event_id") or "")
        if not event_id or event_id in known or item.get("status") not in VALID_STATUSES:
            continue
        item.setdefault("created_at", _now())
        known.add(event_id)
        added.append(item)
    if added:
        with path.open("a", encoding="utf-8") as handle:
            for item in added:
                handle.write(json.dumps(item, sort_keys=True, default=str) + "\n")
    return added


def _outcome_status(item: dict[str, Any]) -> str | None:
    raw = str(item.get("status") or item.get("outcome") or "").lower()
    if raw in {"accepted", "fixed", "verified", "confirmed", "true_positive"}:
        return "verified"
    if raw in {"rejected", "false_positive", "dismissed"}:
        return "rejected"
    return "superseded" if raw == "superseded" else None


def record_human_outcomes(root: str | Path, outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Promote only explicit human/Judge outcomes into the experience ledger."""

    events: list[dict[str, Any]] = []
    for item in outcomes:
        if not isinstance(item, dict):
            continue
        status = _outcome_status(item)
        if status is None:
            continue
        mission_id = item.get("mission_id")
        category = str(item.get("category") or "other").lower()
        officer = str(item.get("officer") or OFFICER_BY_CATEGORY.get(category, "Analyst"))
        finding_id = str(item.get("finding_id") or item.get("id") or item.get("message") or "unknown")
        event_type = {
            "verified": "confirmed_finding",
            "rejected": "rejected_finding",
            "superseded": "superseded_finding",
        }[status]
        common = {
            "mission_id": mission_id,
            "finding_id": finding_id,
            "event_type": event_type,
            "status": status,
            "category": category,
            "path": item.get("path"),
            "message": item.get("message") or item.get("lesson") or finding_id,
            "evidence_refs": item.get("evidence_refs") or item.get("evidence") or [],
            "outcome": item.get("outcome") or item.get("status"),
            "source": "human_or_judge_outcome",
        }
        for subject_type, subject_id in (("cpl", "Cpl"), ("officer", officer)):
            events.append({
                **common,
                "event_id": _stable_id(mission_id, subject_type, subject_id, finding_id, status, item.get("path")),
                "subject_type": subject_type,
                "subject_id": subject_id,
            })
        models = item.get("supporting_models") or ([item.get("model")] if item.get("model") else [])
        for model in dict.fromkeys(str(model) for model in models if model):
            events.append({
                **common,
                "event_id": _stable_id(mission_id, "model", model, finding_id, status, item.get("path")),
                "subject_type": "model",
                "subject_id": model,
            })
        for weapon in dict.fromkeys(str(weapon) for weapon in item.get("weapons", []) if weapon):
            events.append({
                **common,
                "event_id": _stable_id(mission_id, "weapon", weapon, finding_id, status, item.get("path")),
                "subject_type": "weapon",
                "subject_id": weapon,
            })
    return append_experience_events(root, events)


def derive_profiles(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[f"{event.get('subject_type')}:{event.get('subject_id')}"] .append(event)
    profiles: dict[str, dict[str, Any]] = {}
    for key, rows in grouped.items():
        verified = sum(item.get("status") == "verified" for item in rows)
        rejected = sum(item.get("status") == "rejected" for item in rows)
        total = max(1, verified + rejected)
        mission_ids = {str(item.get("mission_id")) for item in rows if item.get("mission_id") is not None}
        profiles[key] = {
            "subject_type": rows[-1].get("subject_type"),
            "subject_id": rows[-1].get("subject_id"),
            "missions_recorded": len(mission_ids) if mission_ids else len(rows),
            "outcomes_recorded": len(rows),
            "verified_outcomes": verified,
            "rejected_outcomes": rejected,
            "observed_reliability": round(verified / total, 3),
            "categories": sorted({str(item.get("category")) for item in rows if item.get("category")}),
            "last_event_id": rows[-1].get("event_id"),
        }
    return profiles


def _path_related(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if previous == current:
        return True
    previous_parent = previous.rsplit("/", 1)[0] if "/" in previous else ""
    current_parent = current.rsplit("/", 1)[0] if "/" in current else ""
    return bool(previous_parent and previous_parent == current_parent)


def retrieve_experience(root: str | Path, changed_files: list[str], *, officers: Iterable[str] = (), limit: int = 16) -> dict[str, Any]:
    """Return relevant verified/rejected experience for the current mission."""

    mission_tokens = _tokens(" ".join(changed_files))
    officer_set = {str(item).lower() for item in officers}
    events = load_experience_events(root)
    ranked: list[tuple[float, dict[str, Any]]] = []
    for event in events:
        score = 0.0
        path = str(event.get("path") or "")
        if any(_path_related(path, changed) for changed in changed_files):
            score += 4.0
        overlap = len(mission_tokens & _tokens(" ".join([path, str(event.get("message")), str(event.get("category"))])))
        score += min(3.0, overlap * 0.5)
        if score > 0 and event.get("subject_type") == "officer" and str(event.get("subject_id", "")).lower() in officer_set:
            score += 2.0
        if score > 0 and event.get("status") == "verified":
            score += 0.5
        if score > 0:
            ranked.append((score, event))
    ranked.sort(key=lambda pair: (pair[0], str(pair[1].get("created_at", ""))), reverse=True)

    lessons: list[dict[str, Any]] = []
    for record in ReviewMemoryStore(default_memory_path(root)).load():
        if record.status not in {"verified", "rejected"}:
            continue
        text = " ".join([*record.applies_to, record.summary, record.reason, *record.tags])
        if any(path in changed_files for path in record.applies_to) or mission_tokens & _tokens(text):
            lessons.append({
                "id": record.id,
                "status": record.status,
                "lesson": record.summary,
                "risk": record.reason,
                "applicable_paths": record.applies_to,
                "confidence": record.confidence,
            })

    return {
        "checked": True,
        "events": [event for _, event in ranked[: max(1, limit)]],
        "canonical_lessons": lessons[: max(1, limit // 2)],
        "profiles": derive_profiles(events),
        "anti_repeat_rule": "Applicable verified experience must influence the mission or Cpl must record why it was not used.",
    }


def detect_recurrences(findings: list[dict[str, Any]], experience: dict[str, Any]) -> list[dict[str, Any]]:
    recurrences: list[dict[str, Any]] = []
    for finding in findings:
        current_tokens = _tokens(" ".join([str(finding.get("message")), str(finding.get("category")), str(finding.get("path"))]))
        best: tuple[float, dict[str, Any]] | None = None
        for event in experience.get("events", []):
            if event.get("status") != "verified":
                continue
            previous_tokens = _tokens(" ".join([str(event.get("message")), str(event.get("category")), str(event.get("path"))]))
            score = len(current_tokens & previous_tokens) / max(1, len(current_tokens | previous_tokens))
            if finding.get("path") and finding.get("path") == event.get("path"):
                score += 0.4
            if best is None or score > best[0]:
                best = (score, event)
        if best and best[0] >= 0.45:
            recurrences.append({
                "current_finding": finding.get("message"),
                "previous_event_id": best[1].get("event_id"),
                "previous_message": best[1].get("message"),
                "similarity": round(min(1.0, best[0]), 3),
                "required_response": "Check why the previous prevention failed and strengthen regression proof.",
            })
    return recurrences
