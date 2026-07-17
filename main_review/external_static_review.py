"""Static-first review policy for unfamiliar external repositories.

THETECHGUY release proof remains strict for Sergeant's own repositories.  This
mode reviews third-party code without pretending their repository follows the
same release process, while preserving concrete code, contract, security, and
runtime findings through the normal permanent-officer council.
"""

from __future__ import annotations

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
from .static_semantic_review import run_static_semantic_review
from .verdict import decide_verdict, review_repository


def _normalize_path(value: object) -> str:
    return str(value or "").strip().replace("\\", "/").lstrip("./")


def _strict_changed_scope(repository_review: dict[str, Any], changed_files: Iterable[str]) -> dict[str, Any]:
    """Remove unrelated repository-wide history from an external change gate."""

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


def run_external_static_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    """Run the normal Sergeant formation with an external static-review policy."""

    root_path = Path(root).resolve()
    requested = [str(item) for item in changed_files if str(item)]
    changed = [path for path in requested if (root_path / path).is_file()]
    unavailable = [path for path in requested if path not in changed]
    semantic_files = semantic_review_files(root_path, changed)

    repository_review = _strict_changed_scope(review_repository(root_path), changed)
    diff = normalize_diff_review(review_changed_files(changed), root_path, changed)
    standard = _external_standard(root_path, changed)
    capabilities = normalize_capability_review(run_capability_engine(root_path, changed), root_path)
    semantic = run_static_semantic_review(root_path, semantic_files or changed)
    capability_findings = [dict(item) for item in capabilities.get("findings", []) if isinstance(item, dict)]
    capability_findings.extend(dict(item) for item in semantic.get("findings", []) if isinstance(item, dict))
    capabilities = {
        **capabilities,
        "findings": capability_findings,
        "finding_count": len(capability_findings),
        "static_semantic_review": semantic,
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
    consensus = build_consensus([
        {
            "source": "officer-council",
            "verdict": officer_council.get("verdict"),
            "evidence": officer_council.get("admitted_findings", []),
        }
    ])
    verdict = _decide(repository_review, standard, diff, intelligence, challenge, cpl, consensus, officer_council)
    return {
        "schema_version": "sergeant.external-static-review.v1",
        "policy_profile": "external_static",
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
