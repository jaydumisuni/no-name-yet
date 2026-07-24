#!/usr/bin/env python3
"""Collect sanitized, provenance-complete bug-fix lineages for self-learning."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from main_review.cross_repo_learning import CrossRepositorySignalError, classify_signal

try:
    from scripts import select_opaque_transfer_candidates as base
    from scripts.select_opaque_transfer_candidates_v8 import _qualifies_v8
except ImportError:  # Direct execution as python scripts/<name>.py.
    import select_opaque_transfer_candidates as base
    from select_opaque_transfer_candidates_v8 import _qualifies_v8

_SHA = re.compile(r"^[0-9a-f]{40}$")
MAX_CANDIDATES_PER_REPOSITORY = 8
PROCESSED_SIGNAL_STATES = {
    "council_complete",
    "controls_passed",
    "transfer_passed",
    "promotion_ready",
    "accepted",
    "rejected",
}
LIFECYCLE_WORDS = {
    "async", "await", "thread", "lock", "queue", "session", "runtime",
    "endpoint", "connection", "stream", "socket", "lifecycle", "state",
}


def _case_id(repository: str, number: int, defective: str) -> str:
    digest = hashlib.sha256(f"{repository}#{number}:{defective}".encode()).hexdigest()[:12]
    return f"learn-{digest}"


def _changed_lines(rows: list[dict[str, Any]], sources: set[str]) -> int:
    total = 0
    for row in rows:
        if str(row.get("filename") or "") in sources:
            total += int(row.get("additions", 0) or 0)
            total += int(row.get("deletions", 0) or 0)
    return max(1, total)


def _package_count(paths: list[str]) -> int:
    packages = set()
    for raw in paths:
        parts = Path(raw.replace("\\", "/")).parts
        packages.add("/".join(parts[:2]) if len(parts) >= 2 else parts[0])
    return max(1, len(packages))


def _dependency_depth(paths: list[str]) -> int:
    return max((max(0, len(Path(path).parts) - 1) for path in paths), default=0)


def _lifecycle_risk(paths: list[str]) -> bool:
    words = set()
    for path in paths:
        words.update(re.split(r"[^a-z0-9]+", path.lower()))
    return bool(words & LIFECYCLE_WORDS)


def _bounded_positive_int(value: object, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return max(1, fallback)
    return max(1, number)


def _bounded_novelty(value: object, fallback: float = 0.85) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = fallback
    return max(0.0, min(1.0, number))


def _signal_candidates(signals_dir: Path | None) -> list[dict[str, Any]]:
    """Load unprocessed, provenance-complete direct-event candidates."""

    if signals_dir is None or not signals_dir.is_dir():
        return []
    selected: list[dict[str, Any]] = []
    for path in sorted(signals_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid learning signal {path}: {error}") from error
        if not isinstance(payload, dict):
            raise ValueError(f"learning signal must be an object: {path}")
        learning_state = str(payload.get("learning_state") or "collected").strip().lower()
        if learning_state in PROCESSED_SIGNAL_STATES:
            continue
        try:
            classification = classify_signal(payload)
        except CrossRepositorySignalError as error:
            raise ValueError(f"invalid learning signal {path}: {error}") from error
        if classification.get("disposition") != "candidate_ready":
            continue
        candidate = dict(classification["candidate"])
        scored_paths = list(candidate["scored_paths"])
        candidate.update({
            "changed_files": _bounded_positive_int(payload.get("changed_files"), len(scored_paths)),
            "changed_lines": _bounded_positive_int(payload.get("changed_lines"), len(scored_paths) * 40),
            "package_count": _bounded_positive_int(payload.get("package_count"), _package_count(scored_paths)),
            "dependency_depth": max(0, int(payload.get("dependency_depth", _dependency_depth(scored_paths)) or 0)),
            "cross_component": bool(payload.get("cross_component")),
            "concurrency_or_lifecycle": bool(payload.get("concurrency_or_lifecycle")),
            "security_or_integrity": bool(payload.get("security_or_integrity")),
            "defect_novelty": _bounded_novelty(payload.get("defect_novelty")),
            "signal_digest": classification["signal_digest"],
            "signal_path": path.as_posix(),
            "learning_objectives": [
                str(item).strip()
                for item in payload.get("learning_objectives", [])
                if str(item).strip()
            ],
            "direct_event_candidate": True,
        })
        selected.append(candidate)
    selected.sort(key=lambda row: (
        -float(row.get("defect_novelty", 0.0) or 0.0),
        str(row.get("repository") or ""),
        str(row.get("case_id") or ""),
    ))
    return selected


def _candidate_for_repo(
    *, repository: str, language: str, suffixes: set[str], headers: dict[str, str], used: set[str],
) -> dict[str, Any] | None:
    if repository in used:
        return None
    candidates: list[dict[str, Any]] = []
    seen: set[int] = set()
    for query in (
        f"repo:{repository} is:pr is:merged label:bug",
        f"repo:{repository} is:pr is:merged in:title fix",
    ):
        for item in base._search(query, headers):
            number = int(item.get("number") or 0)
            if number and number not in seen:
                seen.add(number)
                candidates.append(item)
            if len(candidates) >= MAX_CANDIDATES_PER_REPOSITORY:
                break
        if len(candidates) >= MAX_CANDIDATES_PER_REPOSITORY:
            break

    owner, name = repository.split("/", 1)
    for item in candidates[:MAX_CANDIDATES_PER_REPOSITORY]:
        number = int(item.get("number") or 0)
        if not number:
            continue
        pr = base._api(f"/repos/{owner}/{name}/pulls/{number}", headers)
        if not isinstance(pr, dict) or not pr.get("merged_at"):
            continue
        defective = str((pr.get("base") or {}).get("sha") or "").lower()
        fixing = str((pr.get("head") or {}).get("sha") or "").lower()
        if not _SHA.fullmatch(defective) or not _SHA.fullmatch(fixing) or defective == fixing:
            continue
        try:
            rows = base._pr_files(repository, number, headers)
        except base.IncompletePullRequestFileList:
            continue
        sources = base._eligible_sources(rows, suffixes)
        if not 1 <= len(sources) <= 12:
            continue
        if not _qualifies_v8(pr, rows, sources):
            continue
        compare = base._api(f"/repos/{owner}/{name}/compare/{defective}...{fixing}", headers)
        if not isinstance(compare, dict):
            continue
        if str((compare.get("merge_base_commit") or {}).get("sha") or "").lower() != defective:
            continue
        if str(compare.get("status") or "") != "ahead" or int(compare.get("ahead_by") or 0) < 1:
            continue
        source_set = set(sources)
        return {
            "case_id": _case_id(repository, number, defective),
            "repository": repository,
            "source_pr": number,
            "defective_ref": defective,
            "fixing_ref": fixing,
            "scored_paths": sources,
            "language": language,
            "changed_files": len(sources),
            "changed_lines": _changed_lines(rows, source_set),
            "package_count": _package_count(sources),
            "dependency_depth": _dependency_depth(sources),
            "cross_component": _package_count(sources) > 1,
            "concurrency_or_lifecycle": _lifecycle_risk(sources),
            "defect_novelty": 0.5,
            "provenance_complete": True,
        }
    return None


def collect(
    *, reviewer: str, week_id: str, pool: list[dict[str, Any]], limit: int,
    signals_dir: Path | None = None,
) -> dict[str, Any]:
    reviewer = reviewer.lower().strip()
    if not _SHA.fullmatch(reviewer):
        raise ValueError("reviewer must be a full frozen commit SHA")
    token = os.environ.get("GH_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"sergeant-self-learning-{week_id}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    used = base._prior_repositories(week_id)
    selected: list[dict[str, Any]] = []
    direct_candidates = _signal_candidates(signals_dir)
    for candidate in direct_candidates:
        if len(selected) >= limit:
            break
        case_id = str(candidate.get("case_id") or "")
        if case_id and any(row.get("case_id") == case_id for row in selected):
            continue
        selected.append(candidate)
        used.add(str(candidate["repository"]))

    for lane in pool:
        if len(selected) >= limit:
            break
        language = str(lane.get("language") or lane.get("lane") or "unknown").strip().lower()
        suffixes = {str(value).lower() for value in lane.get("suffixes", [])}
        repositories = [str(value) for value in lane.get("repos", [])]
        if not suffixes or not repositories:
            continue
        for repository in repositories:
            candidate = _candidate_for_repo(
                repository=repository,
                language=language,
                suffixes=suffixes,
                headers=headers,
                used=used,
            )
            if candidate is not None:
                selected.append(candidate)
                used.add(repository)
                break

    return {
        "schema_version": "sergeant.github-learning-candidates.v1",
        "week_id": week_id,
        "reviewer_frozen_before_collection": reviewer,
        "truth_persisted_before_blind_review": False,
        "complete_pr_file_pagination_required": True,
        "capability_addition_exclusion": True,
        "preexisting_behavioral_contract_evidence_required": True,
        "feature_enablement_without_defect_rejected": True,
        "production_source_only": True,
        "max_candidates_per_repository": MAX_CANDIDATES_PER_REPOSITORY,
        "direct_signal_candidate_count": sum(1 for row in selected if row.get("direct_event_candidate") is True),
        "candidate_count": len(selected),
        "candidates": selected,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--week-id", required=True)
    parser.add_argument("--pool-json", type=Path, required=True)
    parser.add_argument("--signals-dir", type=Path, default=Path(".github/self-learning/signals"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()
    pool = json.loads(args.pool_json.read_text(encoding="utf-8"))
    if not isinstance(pool, list):
        raise ValueError("pool JSON must be a list")
    packet = collect(
        reviewer=args.reviewer,
        week_id=args.week_id,
        pool=pool,
        limit=max(1, min(12, args.limit)),
        signals_dir=args.signals_dir,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "week_id": args.week_id,
        "candidate_count": packet["candidate_count"],
        "direct_signal_candidate_count": packet["direct_signal_candidate_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
