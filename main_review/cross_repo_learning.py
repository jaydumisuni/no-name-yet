"""Governed intake for learning signals originating outside Sergeant.

The intake keeps raw repository activity separate from permanent lessons. Any
THETECHGUY or external repository may supply a signal, but only a provenance-
complete behavioral defect/fix lineage can become a self-learning candidate.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from .operational_contracts import private_force_size

SIGNAL_SCHEMA = "sergeant.cross-repository-learning-signal.v1"
CLASSIFICATION_SCHEMA = "sergeant.cross-repository-learning-classification.v1"
_SOURCE_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SECRET_RE = re.compile(
    r"(?i)(?:github_pat_[A-Za-z0-9_]+|ghp_[A-Za-z0-9]+|sk-[A-Za-z0-9]{20,}|"
    r"(?:api[_-]?key|authorization|bearer|password|passwd|secret|token)\s*[:=]\s*[^\s,;]+)"
)
_ALLOWED_EVENT_KINDS = {
    "commit",
    "pull_request",
    "workflow_run",
    "review_finding",
    "runtime_log",
    "shell_trace",
    "test_failure",
    "repair",
    "release_failure",
}
_EVIDENCE_ONLY_FLAGS = ("formatting_only", "style_only", "docs_only", "no_behavior_change")


class CrossRepositorySignalError(ValueError):
    """Raised when a cross-repository signal violates the intake contract."""


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _clean_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _validate_signal(signal: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(signal)
    repository = str(payload.get("repository") or "").strip()
    event_kind = str(payload.get("event_kind") or "").strip().lower()
    source_url = str(payload.get("source_url") or "").strip()
    if not _SOURCE_RE.fullmatch(repository):
        raise CrossRepositorySignalError("repository must use owner/name form")
    if event_kind not in _ALLOWED_EVENT_KINDS:
        raise CrossRepositorySignalError(f"unsupported event kind: {event_kind or 'missing'}")
    repository_url = f"https://github.com/{repository}"
    if source_url != repository_url and not source_url.startswith(f"{repository_url}/"):
        raise CrossRepositorySignalError("source_url must identify the declared GitHub repository")
    source_event_url = str(payload.get("source_event_url") or "").strip()
    if source_event_url and source_event_url != repository_url and not source_event_url.startswith(f"{repository_url}/"):
        raise CrossRepositorySignalError("source_event_url must identify the declared GitHub repository")
    serialized = json.dumps(payload, sort_keys=True, default=str)
    if _SECRET_RE.search(serialized):
        raise CrossRepositorySignalError("signal contains credential-like material")
    payload["repository"] = repository
    payload["event_kind"] = event_kind
    payload["source_url"] = source_url
    if source_event_url:
        payload["source_event_url"] = source_event_url
    payload["scored_paths"] = _clean_string_list(payload.get("scored_paths"))
    payload["evidence_refs"] = _clean_string_list(payload.get("evidence_refs"))
    if payload.get("source_pr") is not None:
        try:
            source_pr = int(payload["source_pr"])
        except (TypeError, ValueError) as error:
            raise CrossRepositorySignalError("source_pr must be a positive integer") from error
        if source_pr < 1:
            raise CrossRepositorySignalError("source_pr must be a positive integer")
        payload["source_pr"] = source_pr
    return payload


def _human_equivalent_workers(signal: Mapping[str, Any]) -> int:
    workers = 2
    if signal.get("event_kind") in {"workflow_run", "review_finding", "release_failure"}:
        workers += 1
    workers += int(bool(signal.get("cross_component")))
    workers += int(bool(signal.get("security_or_integrity")))
    workers += int(bool(signal.get("concurrency_or_lifecycle")))
    path_count = len(signal.get("scored_paths", []))
    workers += min(4, path_count // 4)
    return max(2, min(12, workers))


def _has_lineage(signal: Mapping[str, Any]) -> bool:
    defective = str(signal.get("defective_ref") or "").lower()
    fixing = str(signal.get("fixing_ref") or "").lower()
    return bool(
        _SHA_RE.fullmatch(defective)
        and _SHA_RE.fullmatch(fixing)
        and defective != fixing
        and (signal.get("source_pr") or signal.get("source_event_url"))
    )


def _candidate_complete(signal: Mapping[str, Any]) -> bool:
    return bool(
        _has_lineage(signal)
        and signal.get("defect_confirmed") is True
        and signal.get("fix_verified") is True
        and signal.get("blind_review_possible") is True
        and str(signal.get("language") or "").strip()
        and signal.get("scored_paths")
        and signal.get("evidence_refs")
    )


def classify_signal(signal: Mapping[str, Any]) -> dict[str, Any]:
    """Classify a repository event without promoting or merging anything."""

    payload = _validate_signal(signal)
    human_workers = _human_equivalent_workers(payload)
    classification: dict[str, Any] = {
        "schema_version": CLASSIFICATION_SCHEMA,
        "signal_schema": SIGNAL_SCHEMA,
        "signal_digest": _canonical_digest(payload),
        "repository": payload["repository"],
        "event_kind": payload["event_kind"],
        "source_url": payload["source_url"],
        "human_equivalent_workers": human_workers,
        "triage_private_count": private_force_size(human_workers),
        "authority": {
            "may_auto_promote": False,
            "may_auto_merge": False,
            "final_verdict": "Sergeant",
        },
    }

    if any(payload.get(flag) is True for flag in _EVIDENCE_ONLY_FLAGS) or payload.get("behavior_change") is False:
        classification.update({
            "disposition": "evidence_only",
            "reason": "signal does not establish a behavioral defect/fix lesson",
            "candidate": None,
        })
        return classification

    if _candidate_complete(payload):
        classification.update({
            "disposition": "candidate_ready",
            "reason": "provenance-complete behavioral lineage can enter the governed queue",
            "candidate": to_queue_candidate(payload),
        })
        return classification

    has_useful_context = bool(
        payload.get("source_ref")
        or payload.get("source_pr")
        or payload.get("source_event_url")
        or payload.get("evidence_refs")
        or payload.get("scored_paths")
        or payload.get("summary")
    )
    classification.update({
        "disposition": "needs_lineage" if has_useful_context else "rejected",
        "reason": (
            "retain as a signal until defective/fixing lineage and verification are recovered"
            if has_useful_context
            else "signal lacks enough source context for governed triage"
        ),
        "candidate": None,
    })
    return classification


def to_queue_candidate(signal: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a fully qualified signal into the existing governed queue shape."""

    payload = _validate_signal(signal)
    if not _candidate_complete(payload):
        raise CrossRepositorySignalError(
            "candidate requires a verified defect/fix lineage, blind-review boundary, language, paths, and evidence"
        )
    repository = payload["repository"]
    defective = str(payload["defective_ref"]).lower()
    seed = f"{repository}:{payload.get('source_pr') or payload.get('source_event_url')}:{defective}"
    case_id = str(payload.get("case_id") or f"learn-{hashlib.sha256(seed.encode()).hexdigest()[:12]}")
    human_workers = _human_equivalent_workers(payload)
    candidate = {
        "case_id": case_id,
        "repository": repository,
        "defective_ref": defective,
        "fixing_ref": str(payload["fixing_ref"]).lower(),
        "scored_paths": list(payload["scored_paths"]),
        "language": str(payload["language"]).strip().lower(),
        "source_event_url": str(payload.get("source_event_url") or payload["source_url"]),
        "source_event_kind": payload["event_kind"],
        "evidence_refs": list(payload["evidence_refs"]),
        "provenance_complete": True,
        "cross_repository": repository != "jaydumisuni/Sergeant",
        "human_equivalent_workers": human_workers,
        "private_count": private_force_size(human_workers),
    }
    if payload.get("source_pr"):
        candidate["source_pr"] = int(payload["source_pr"])
    return candidate
