"""Independent PR reviewer for Sergeant.

This module is the reviewer entry point. It combines repository evidence, changed
file risk, Tier 1 capability analysis, the engineering standard, challenge mode,
decision workspace, and consensus into one review packet. External tools are
optional inputs, not gates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .capability_engine import run_capability_engine
from .challenge import run_challenge_mode
from .consensus import build_consensus
from .decision_workspace import build_decision_workspace
from .diff_review import review_changed_files
from .review_ingestion import ingest_external_review_file
from .standard_engine import run_standard_engine
from .verdict import review_repository


@dataclass(frozen=True)
class ReviewVerdict:
    verdict: str
    confidence: float
    reason: str
    required_actions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _required_actions(
    repository_review: dict[str, Any],
    standard: dict[str, Any],
    diff: dict[str, Any],
    capabilities: dict[str, Any],
) -> list[str]:
    actions: list[str] = []
    repo_verdict = repository_review.get("verdict", {})
    if isinstance(repo_verdict, dict) and repo_verdict.get("verdict") != "PASS":
        actions.append(str(repo_verdict.get("suggested_next_action", "Fix repository review findings.")))
    for blocker in standard.get("blockers", []):
        actions.append(str(blocker))
    diff_verdict = diff.get("verdict", {}) if isinstance(diff, dict) else {}
    if isinstance(diff_verdict, dict) and diff_verdict.get("verdict") != "PASS":
        actions.append(str(diff_verdict.get("suggested_next_action", "Answer changed-file review findings.")))
    if capabilities.get("verdict") in {"BLOCK", "NEEDS WORK"}:
        for finding in capabilities.get("findings", []):
            if finding.get("severity") in {"blocker", "major"}:
                actions.append(f"Answer {finding.get('capability')} finding: {finding.get('message')}")
    return sorted(set(action for action in actions if action))


def _decide(
    repository_review: dict[str, Any],
    standard: dict[str, Any],
    diff: dict[str, Any],
    capabilities: dict[str, Any],
    challenge: dict[str, Any],
    consensus: dict[str, Any],
) -> ReviewVerdict:
    actions = _required_actions(repository_review, standard, diff, capabilities)
    consensus_value = consensus.get("consensus")
    if actions or consensus_value == "BLOCK":
        return ReviewVerdict(
            verdict="REQUEST_CHANGES",
            confidence=0.88,
            reason="Blocking evidence, Tier 1 capability risk, or required action remains unanswered.",
            required_actions=actions,
        )
    if consensus_value == "NEEDS WORK" or capabilities.get("verdict") == "NEEDS WORK":
        return ReviewVerdict(
            verdict="COMMENT",
            confidence=0.76,
            reason="Review found non-blocking concerns that should be considered before merge.",
            required_actions=actions,
        )
    return ReviewVerdict(
        verdict="APPROVE",
        confidence=float(challenge.get("confidence_after_challenge", 0.8)),
        reason="Repository evidence, Tier 1 capability analysis, standard checks, diff review, challenge mode, and consensus are satisfied.",
        notes=["External reviewer comments are optional learning inputs, not required gates."],
    )


def run_independent_pr_review(
    root: str | Path = ".",
    *,
    changed_files: list[str] | None = None,
    external_review_file: str | Path | None = None,
) -> dict[str, Any]:
    root_path = Path(root)
    changed = changed_files or []
    repository_review = review_repository(root_path)
    diff = review_changed_files(changed)
    standard = run_standard_engine(root_path, changed)
    capabilities = run_capability_engine(root_path, changed)
    challenge = run_challenge_mode(repository_review)

    external_workspace = {"summary": {"total": 0}, "decisions": [], "ready_for_memory": []}
    if external_review_file is not None:
        ingestion = ingest_external_review_file(external_review_file)
        external_workspace = build_decision_workspace(ingestion["comments"])

    consensus = build_consensus(
        [
            {"source": "main-review", "verdict": repository_review.get("verdict", {}).get("verdict"), "evidence": repository_review.get("evidence", {}).get("findings", [])},
            {"source": "diff-review", "verdict": diff.get("verdict", {}).get("verdict"), "evidence": diff.get("evidence", {}).get("findings", [])},
            {"source": "capability-engine", "verdict": capabilities.get("verdict"), "evidence": capabilities.get("findings", [])},
            {"source": "standard-engine", "verdict": "PASS" if standard.get("passed") else "NEEDS WORK", "evidence": standard.get("blockers", [])},
            {"source": "challenge-mode", "verdict": "PASS" if challenge.get("trusted") else "NEEDS WORK", "evidence": challenge.get("challenges", [])},
        ]
    )
    verdict = _decide(repository_review, standard, diff, capabilities, challenge, consensus)
    return {
        "verdict": verdict.to_dict(),
        "repository_review": repository_review.get("verdict", {}),
        "diff_review": diff.get("verdict", {}),
        "capability_review": capabilities,
        "standard": standard,
        "challenge": challenge,
        "external_decisions": external_workspace,
        "consensus": consensus,
        "changed_files": changed,
    }


def render_pr_review_markdown(packet: dict[str, Any]) -> str:
    verdict = packet.get("verdict", {})
    lines = [
        "# Sergeant Review",
        "",
        f"Verdict: **{verdict.get('verdict', 'UNKNOWN')}**",
        f"Confidence: **{verdict.get('confidence', 0)}**",
        "",
        str(verdict.get("reason", "")),
    ]
    actions = verdict.get("required_actions", [])
    if actions:
        lines.extend(["", "## Required actions"])
        lines.extend(f"- {action}" for action in actions)
    lines.extend(["", "## Evidence summary"])
    lines.append(f"- Repository verdict: {packet.get('repository_review', {}).get('verdict')}")
    lines.append(f"- Diff verdict: {packet.get('diff_review', {}).get('verdict')}")
    lines.append(f"- Capability verdict: {packet.get('capability_review', {}).get('verdict')}")
    lines.append(f"- Standard passed: {packet.get('standard', {}).get('passed')}")
    lines.append(f"- Challenge trusted: {packet.get('challenge', {}).get('trusted')}")
    lines.append(f"- Consensus: {packet.get('consensus', {}).get('consensus')}")
    capability_status = packet.get("capability_review", {}).get("capability_status", {})
    if capability_status:
        lines.extend(["", "## Tier 1 capabilities"])
        for name, status in capability_status.items():
            lines.append(f"- {name}: {status}")
    lines.extend(["", "## Rule"])
    lines.append("Sergeant is the reviewer. Main Review is the reviewer core. External reviewers are optional evidence sources, not required gates.")
    return "\n".join(lines) + "\n"
