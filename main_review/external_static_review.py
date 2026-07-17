"""Static-first review policy for unfamiliar external repositories.

THETECHGUY release proof remains strict for Sergeant's own repositories.  This
mode reviews third-party code without pretending their repository follows the
same release process, while preserving concrete code, contract, security, and
runtime findings through the normal permanent-officer council.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from .capability_engine import run_capability_engine
from .capability_policy import normalize_capability_review
from .challenge import run_challenge_mode
from .consensus import build_consensus
from .cpl_noise import reconcile_cpl_findings
from .cpl_runtime import run_cpl_review
from .diff_policy import normalize_diff_review
from .diff_review import review_changed_files
from .officer_council import run_officer_council
from .pr_reviewer import _decide
from .review_intelligence import run_review_intelligence
from .review_scope import scope_repository_review
from .semantic_scope import semantic_review_files
from .standard_engine import run_standard_engine
from .static_invariant_review import run_static_invariant_review
from .static_semantic_review import run_static_semantic_review
from .verdict import decide_verdict, review_repository

_SEVERITY_RANK = {"blocker": 4, "major": 3, "minor": 2, "advisory": 1}


def _normalize_path(value: object) -> str:
    return str(value or "").strip().replace("\\", "/").lstrip("./")


def _strict_changed_scope(repository_review: dict[str, Any], changed_files: Iterable[str]) -> dict[str, Any]:
    scoped = scope_repository_review(repository_review, changed_files)
    changed = {_normalize_path(path) for path in changed_files if _normalize_path(path)}
    evidence = dict(scoped.get("evidence") or {})
    rows = [dict(item) for item in evidence.get("findings", []) if isinstance(item, dict)]
    rows = [item for item in rows if _normalize_path(item.get("path")) in changed]
    evidence["findings"] = rows
    evidence["finding_count"] = len(rows)
    scoped["evidence"] = evidence
    scoped["verdict"] = decide_verdict(evidence).to_dict()
    scope = dict(scoped.get("scope") or {})
    scope["policy"] = "external_changed_scope_only"
    scope["scoped_finding_count"] = len(rows)
    scoped["scope"] = scope
    return scoped


def _external_standard(root: Path, changed: list[str]) -> dict[str, Any]:
    standard = run_standard_engine(root, changed)
    original = [str(item) for item in standard.get("blockers", []) if str(item)]
    return {
        **standard,
        "passed": True,
        "blockers": [],
        "policy_profile": "external_static",
        "external_advisories": original,
        "policy_reason": "Repository-release proof is advisory for unfamiliar third-party code; grounded implementation defects still gate through the officer ledger.",
    }


def _snapshot_diff(diff: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(diff.get("evidence") or {})
    rows = [dict(item) for item in evidence.get("findings", []) if isinstance(item, dict)]
    rows = [
        item for item in rows
        if str(item.get("root_cause") or "") != "proof-gap"
        and str(item.get("message") or "").lower() != "implementation changed without changed tests in the same pr."
    ]
    evidence["findings"] = rows
    evidence["finding_count"] = len(rows)
    return {
        **diff,
        "evidence": evidence,
        "verdict": decide_verdict(evidence).to_dict(),
        "snapshot_policy": "Historical snapshots do not assert changed-test obligations from future fix files.",
    }


def _calibrated_semantic_findings(semantic: dict[str, Any]) -> list[dict[str, Any]]:
    selected: dict[tuple[str, str], tuple[int, dict[str, Any]]] = {}
    for raw in semantic.get("findings", []):
        if not isinstance(raw, dict):
            continue
        finding = dict(raw)
        root = str(finding.get("root_cause") or "")
        path = str(finding.get("path") or "")
        priority = 1
        if root == "publication-before-initialization":
            evidence = str(finding.get("evidence") or "")
            relationship = re.search(
                r"(?P<caller>[A-Za-z0-9_$]+) invokes event-emitting helper (?P<callee>[A-Za-z0-9_$]+)",
                evidence,
            )
            if relationship is None:
                continue
            caller = relationship.group("caller")
            callee = relationship.group("callee")
            if not re.search(r"(?:save|cache|store|publish)", callee, re.I):
                continue
            if not re.search(r"(?:setup|create|reset|receiv)", caller, re.I):
                continue
            priority = 3 if re.search(r"(?:setup|create|reset)", caller, re.I) else 2
        key = (root, path)
        current = selected.get(key)
        if current is None or priority > current[0]:
            selected[key] = (priority, finding)
    return [row for _, row in selected.values()]


def _collapse_root_findings(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one user-facing finding per root and path while retaining provenance."""

    collapsed: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        finding = dict(raw)
        key = (
            str(finding.get("root_cause") or finding.get("message") or "unknown"),
            _normalize_path(finding.get("path")),
        )
        reference = str(finding.get("evidence_ref") or "")
        existing = collapsed.get(key)
        if existing is None:
            finding["supporting_evidence_refs"] = sorted({reference} - {""})
            collapsed[key] = finding
            continue

        refs = {
            str(item)
            for item in existing.get("supporting_evidence_refs", [])
            if str(item)
        }
        refs.update(
            str(item)
            for item in finding.get("supporting_evidence_refs", [])
            if str(item)
        )
        if reference:
            refs.add(reference)

        existing_rank = _SEVERITY_RANK.get(str(existing.get("severity") or "").lower(), 0)
        candidate_rank = _SEVERITY_RANK.get(str(finding.get("severity") or "").lower(), 0)
        existing_confidence = float(existing.get("confidence", 0.0) or 0.0)
        candidate_confidence = float(finding.get("confidence", 0.0) or 0.0)
        if (candidate_rank, candidate_confidence) > (existing_rank, existing_confidence):
            representative = finding
        else:
            representative = existing
        representative = dict(representative)
        representative["supporting_evidence_refs"] = sorted(refs)
        line_values = [
            int(value)
            for value in (existing.get("line_start"), finding.get("line_start"))
            if isinstance(value, int) and value > 0
        ]
        if line_values:
            representative["line_start"] = min(line_values)
            representative["line_end"] = max(
                int(existing.get("line_end") or existing.get("line_start") or 0),
                int(finding.get("line_end") or finding.get("line_start") or 0),
            )
            representative["evidence_ref"] = f"{key[1]}:{representative['line_start']}"
        collapsed[key] = representative
    return list(collapsed.values())


def _capability_findings_for_mode(
    capabilities: dict[str, Any], semantic: dict[str, Any], invariants: dict[str, Any], *, review_mode: str,
) -> list[dict[str, Any]]:
    rows = [dict(item) for item in capabilities.get("findings", []) if isinstance(item, dict)]
    if review_mode == "snapshot":
        rows = [
            item for item in rows
            if str(item.get("root_cause") or "") != "proof-gap"
            and str(item.get("message") or "").lower() != "implementation changed without changed tests in the same pr."
        ]
    rows.extend(_calibrated_semantic_findings(semantic))
    rows.extend(dict(item) for item in invariants.get("findings", []) if isinstance(item, dict))
    return _collapse_root_findings(rows)


def run_external_static_review(
    root: str | Path, changed_files: Iterable[str], *, review_mode: str = "change",
) -> dict[str, Any]:
    if review_mode not in {"change", "snapshot"}:
        raise ValueError("review_mode must be 'change' or 'snapshot'")
    root_path = Path(root).resolve()
    requested = [str(item) for item in changed_files if str(item)]
    changed = [path for path in requested if (root_path / path).is_file()]
    unavailable = [path for path in requested if path not in changed]
    semantic_files = semantic_review_files(root_path, changed)

    repository_review = _strict_changed_scope(review_repository(root_path), changed)
    diff = normalize_diff_review(review_changed_files(changed), root_path, changed)
    if review_mode == "snapshot":
        diff = _snapshot_diff(diff)
    standard = _external_standard(root_path, changed)
    capabilities = normalize_capability_review(run_capability_engine(root_path, changed), root_path)
    analysis_scope = semantic_files or changed
    semantic = run_static_semantic_review(root_path, analysis_scope)
    invariants = run_static_invariant_review(root_path, analysis_scope)
    calibrated_semantic = _calibrated_semantic_findings(semantic)
    capability_findings = _capability_findings_for_mode(
        capabilities, semantic, invariants, review_mode=review_mode,
    )
    capabilities = {
        **capabilities,
        "findings": capability_findings,
        "finding_count": len(capability_findings),
        "static_semantic_review": {**semantic, "admitted_candidate_findings": calibrated_semantic},
        "static_invariant_review": invariants,
    }
    intelligence = run_review_intelligence({"capability_review": capabilities})
    challenge = run_challenge_mode(repository_review)

    cpl_context = {
        "review_scope": {
            "changed_files": changed,
            "requested_files": requested,
            "unavailable_requested_files": unavailable,
            "semantic_files": semantic_files,
            "workspace_sample": False,
            "policy_profile": "external_static",
            "review_mode": review_mode,
        },
        "repository_review": repository_review.get("verdict", {}),
        "repository_findings": repository_review.get("evidence", {}).get("findings", []),
        "diff_review": diff.get("verdict", {}),
        "diff_findings": diff.get("evidence", {}).get("findings", []),
        "standard": standard,
        "capability_review": capabilities,
        "review_intelligence": intelligence,
        "challenge": challenge,
    }
    cpl = run_cpl_review(root_path, semantic_files, cpl_context)
    deterministic_findings = [
        *repository_review.get("evidence", {}).get("findings", []),
        *diff.get("evidence", {}).get("findings", []),
        *capabilities.get("findings", []),
        *intelligence.get("promoted_findings", []),
    ]
    cpl = reconcile_cpl_findings(cpl, deterministic_findings)

    officer_council = run_officer_council(
        root_path,
        changed,
        repository_review=repository_review,
        diff=diff,
        capabilities=capabilities,
        intelligence=intelligence,
        standard=standard,
        cpl=cpl,
    )
    cpl = {**cpl, "coordination_status": "completed", "officer_formation": officer_council}
    consensus = build_consensus([{
        "source": "officer-council",
        "verdict": officer_council.get("verdict"),
        "evidence": officer_council.get("admitted_findings", []),
    }])
    verdict = _decide(repository_review, standard, diff, intelligence, challenge, cpl, consensus, officer_council)
    return {
        "schema_version": "sergeant.external-static-review.v1",
        "policy_profile": "external_static",
        "review_mode": review_mode,
        "verdict": verdict.to_dict(),
        "repository_review": repository_review.get("verdict", {}),
        "repository_review_scope": repository_review.get("scope", {}),
        "repository_background": repository_review.get("background", {}),
        "diff_review": diff.get("verdict", {}),
        "diff_review_policy": diff.get("policy_adjustments", []),
        "capability_review": capabilities,
        "review_intelligence": intelligence,
        "cpl_review": cpl,
        "semantic_review": cpl,
        "officer_council": officer_council,
        "semantic_files": semantic_files,
        "standard": standard,
        "challenge": challenge,
        "consensus": consensus,
        "changed_files": changed,
        "requested_files": requested,
        "unavailable_requested_files": unavailable,
        "executed_project_code": False,
    }
