"""Scope repository-wide evidence to the change under review.

Repository scanners are intentionally broad. Pull-request review should retain
that broad evidence as context without allowing unrelated historical findings
to dominate the current change. Global credential/safety blockers remain in
scope, while ordinary path findings must connect to a changed file.
"""
from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath
from typing import Any, Iterable

from .verdict import decide_verdict

_ALWAYS_SCOPED_CATEGORIES = {
    "credential",
    "credentials",
    "secret",
    "secrets",
    "public-safety",
    "public_safety",
    "security",
}


def _normalized_path(value: object) -> str:
    return str(value or "").strip().replace("\\", "/").lstrip("./")


def _related_path(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    left_path = PurePosixPath(left)
    right_path = PurePosixPath(right)
    return left_path.parent == right_path.parent and left_path.name == right_path.name


def _finding_paths(finding: dict[str, Any]) -> set[str]:
    paths = {_normalized_path(finding.get("path"))}
    related = finding.get("related_paths")
    if isinstance(related, Iterable) and not isinstance(related, (str, bytes, dict)):
        paths.update(_normalized_path(item) for item in related)
    return {path for path in paths if path}


def is_scope_relevant(finding: dict[str, Any], changed_files: Iterable[str]) -> bool:
    """Return whether a repository finding belongs in the current change gate."""

    changed = {_normalized_path(path) for path in changed_files if _normalized_path(path)}
    if not changed:
        return True
    category = str(finding.get("category") or "").strip().lower()
    severity = str(finding.get("severity") or "").strip().lower()
    if category in _ALWAYS_SCOPED_CATEGORIES and severity in {"blocker", "major"}:
        return True
    paths = _finding_paths(finding)
    return any(_related_path(path, changed_path) for path in paths for changed_path in changed)


def _counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counter = Counter(str(item.get("severity") or "unknown") for item in findings)
    return {key: counter[key] for key in sorted(counter)}


def scope_repository_review(repository_review: dict[str, Any], changed_files: Iterable[str]) -> dict[str, Any]:
    """Return a PR-scoped repository review and preserved background context."""

    evidence = repository_review.get("evidence") if isinstance(repository_review, dict) else {}
    evidence = dict(evidence) if isinstance(evidence, dict) else {}
    raw_findings = evidence.get("findings")
    raw_findings = [dict(item) for item in raw_findings if isinstance(item, dict)] if isinstance(raw_findings, list) else []
    changed = [_normalized_path(path) for path in changed_files if _normalized_path(path)]
    if not changed:
        result = dict(repository_review)
        result["scope"] = {
            "mode": "repository",
            "changed_files": [],
            "scoped_finding_count": len(raw_findings),
            "background_finding_count": 0,
        }
        result["background"] = {"finding_count": 0, "by_severity": {}, "sample": []}
        return result

    scoped = [item for item in raw_findings if is_scope_relevant(item, changed)]
    background = [item for item in raw_findings if item not in scoped]
    scoped_evidence = dict(evidence)
    scoped_evidence["findings"] = scoped
    scoped_evidence["finding_count"] = len(scoped)
    scoped_evidence["repository_finding_count"] = len(raw_findings)
    scoped_evidence["background_finding_count"] = len(background)
    verdict = decide_verdict(scoped_evidence).to_dict()
    return {
        "verdict": verdict,
        "evidence": scoped_evidence,
        "scope": {
            "mode": "changed_files",
            "changed_files": sorted(set(changed)),
            "repository_finding_count": len(raw_findings),
            "scoped_finding_count": len(scoped),
            "background_finding_count": len(background),
        },
        "background": {
            "finding_count": len(background),
            "by_severity": _counts(background),
            "sample": background[:10],
            "rule": "Background findings remain context only unless they connect to the changed scope or are global credential/public-safety blockers.",
        },
    }
