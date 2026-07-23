"""Governed queue for Sergeant's self-learning curriculum.

The queue records every transition and never grants automatic merge or lesson
promotion. A case can become promotion-ready only after a frozen blind result,
truth reveal, three independent worker packets, negative controls, and an
unrelated-language transfer result.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

QUEUE_SCHEMA = "sergeant.self-learning-queue.v1"
STATES = (
    "collected",
    "blind_frozen",
    "truth_revealed",
    "council_complete",
    "controls_passed",
    "transfer_passed",
    "promotion_ready",
    "rejected",
)
_ALLOWED = {
    "collected": {"blind_frozen", "rejected"},
    "blind_frozen": {"truth_revealed", "rejected"},
    "truth_revealed": {"council_complete", "rejected"},
    "council_complete": {"controls_passed", "rejected"},
    "controls_passed": {"transfer_passed", "rejected"},
    "transfer_passed": {"promotion_ready", "rejected"},
    "promotion_ready": set(),
    "rejected": set(),
}


class QueueContractError(ValueError):
    """Raised when a queue transition violates the learning contract."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def new_queue(week_id: str, *, authority_head: str, target_branch: str) -> dict[str, Any]:
    if not week_id.strip() or len(authority_head) != 40:
        raise QueueContractError("week id and full authority head are required")
    return {
        "schema_version": QUEUE_SCHEMA,
        "week_id": week_id,
        "authority_head": authority_head.lower(),
        "target_branch": target_branch,
        "created_at": _now(),
        "authority": {
            "may_auto_merge": False,
            "may_auto_promote": False,
            "final_verdict": "Sergeant",
        },
        "cases": [],
        "events": [],
    }


def add_case(queue: dict[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    case_id = str(candidate.get("case_id") or "").strip()
    if not case_id:
        raise QueueContractError("candidate requires case_id")
    if any(row.get("case_id") == case_id for row in queue.get("cases", [])):
        raise QueueContractError(f"duplicate case id: {case_id}")
    required = ("repository", "defective_ref", "fixing_ref", "scored_paths", "language")
    missing = [field for field in required if not candidate.get(field)]
    if missing:
        raise QueueContractError(f"candidate {case_id} missing: {', '.join(missing)}")
    if not candidate.get("source_pr") and not candidate.get("source_event_url"):
        raise QueueContractError(f"candidate {case_id} requires source_pr or source_event_url")
    case = {
        **dict(candidate),
        "state": "collected",
        "created_at": _now(),
        "artifacts": {},
        "workers": {},
        "decision": None,
    }
    queue.setdefault("cases", []).append(case)
    queue.setdefault("events", []).append({"case_id": case_id, "from": None, "to": "collected", "at": _now()})
    return case


def get_case(queue: Mapping[str, Any], case_id: str) -> dict[str, Any]:
    for row in queue.get("cases", []):
        if isinstance(row, dict) and row.get("case_id") == case_id:
            return row
    raise QueueContractError(f"unknown case: {case_id}")


def transition(
    queue: dict[str, Any],
    case_id: str,
    target: str,
    *,
    artifact_name: str | None = None,
    artifact: Mapping[str, Any] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    if target not in STATES:
        raise QueueContractError(f"unknown target state: {target}")
    case = get_case(queue, case_id)
    current = str(case.get("state"))
    if target not in _ALLOWED.get(current, set()):
        raise QueueContractError(f"invalid transition {current} -> {target}")
    if target == "rejected" and not reason:
        raise QueueContractError("rejection requires a reason")
    if artifact_name:
        if artifact is None:
            raise QueueContractError("artifact payload required")
        case.setdefault("artifacts", {})[artifact_name] = {
            "digest": canonical_digest(artifact),
            "payload": dict(artifact),
        }
    case["state"] = target
    if target == "rejected":
        case["decision"] = {"verdict": "rejected", "reason": reason}
    elif target == "promotion_ready":
        _validate_promotion_readiness(case)
        case["decision"] = {
            "verdict": "promotion_candidate",
            "may_auto_merge": False,
            "may_auto_promote": False,
        }
    queue.setdefault("events", []).append({
        "case_id": case_id,
        "from": current,
        "to": target,
        "at": _now(),
        "reason": reason,
    })
    return case


def attach_worker(queue: dict[str, Any], case_id: str, role: str, packet: Mapping[str, Any]) -> None:
    case = get_case(queue, case_id)
    if case.get("state") != "truth_revealed":
        raise QueueContractError("workers can run only after truth reveal")
    if role not in {"teacher", "prosecutor", "defender"}:
        raise QueueContractError(f"unknown worker role: {role}")
    if packet.get("role") != role or packet.get("case_id") != case_id:
        raise QueueContractError("worker packet binding mismatch")
    case.setdefault("workers", {})[role] = {
        "digest": canonical_digest(packet),
        "payload": dict(packet),
    }


def council_complete(queue: dict[str, Any], case_id: str) -> dict[str, Any]:
    case = get_case(queue, case_id)
    roles = set(case.get("workers", {}))
    if roles != {"teacher", "prosecutor", "defender"}:
        raise QueueContractError("all three isolated workers are required")
    defender = case["workers"]["defender"]["payload"]
    if defender.get("verdict") == "rejects":
        return transition(queue, case_id, "rejected", reason="Defender disproved the proposed lesson")
    return transition(queue, case_id, "council_complete")


def _validate_promotion_readiness(case: Mapping[str, Any]) -> None:
    artifacts = case.get("artifacts", {})
    for required in ("blind_result", "truth_packet", "negative_controls", "transfer_result"):
        if required not in artifacts:
            raise QueueContractError(f"promotion candidate lacks {required}")
    control = artifacts["negative_controls"]["payload"]
    transfer = artifacts["transfer_result"]["payload"]
    if control.get("passed") is not True:
        raise QueueContractError("negative controls must pass")
    if transfer.get("passed") is not True or transfer.get("unrelated_language") is not True:
        raise QueueContractError("unrelated-language transfer must pass")


def write_queue(queue: Mapping[str, Any], path: Path) -> None:
    if queue.get("schema_version") != QUEUE_SCHEMA:
        raise QueueContractError("invalid queue schema")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
