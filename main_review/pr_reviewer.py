"""Independent PR reviewer for Sergeant."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .capability_engine import run_capability_engine
from .capability_policy import normalize_capability_review
from .challenge import run_challenge_mode
from .consensus import build_consensus
from .decision_workspace import build_decision_workspace
from .diff_policy import normalize_diff_review
from .diff_review import review_changed_files
from .llm_review import run_llm_review
from .review_ingestion import ingest_external_review_file
from .review_intelligence import run_review_intelligence
from .semantic_scope import semantic_review_files
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
    intelligence: dict[str, Any],
    semantic: dict[str, Any],
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
    if intelligence.get("verdict") in {"BLOCK", "NEEDS WORK"}:
        for finding in intelligence.get("ranked_findings", []):
            if finding.get("severity") in {"blocker", "major"}:
                actions.append(f"Answer {finding.get('root_cause')} finding: {finding.get('message')}")

    if semantic.get("policy") == "required" and semantic.get("status") in {"unavailable", "error"}:
        actions.append("Configure a reachable FCC or OpenAI-compatible semantic-review model and rerun Sergeant.")
    if semantic.get("verdict") in {"BLOCK", "NEEDS WORK"}:
        for finding in semantic.get("findings", []):
            if finding.get("severity") in {"blocker", "major"}:
                location = f"{finding.get('path')}:{finding.get('line_start')}-{finding.get('line_end')}"
                actions.append(f"Answer semantic {finding.get('severity')} finding at {location}: {finding.get('message')}")
    return sorted(set(action for action in actions if action))


def _decide(
    repository_review: dict[str, Any],
    standard: dict[str, Any],
    diff: dict[str, Any],
    intelligence: dict[str, Any],
    challenge: dict[str, Any],
    semantic: dict[str, Any],
    consensus: dict[str, Any],
) -> ReviewVerdict:
    actions = _required_actions(repository_review, standard, diff, intelligence, semantic)
    consensus_value = consensus.get("consensus")
    intelligence_verdict = intelligence.get("verdict")
    semantic_verdict = semantic.get("verdict")
    notes = ["External reviewer comments are optional learning inputs, not required gates."]
    if semantic.get("status") in {"unavailable", "disabled"} and semantic.get("policy") != "required":
        notes.append("Semantic LLM review was not available; deterministic Sergeant evidence remained authoritative.")
    if semantic.get("status") == "completed_with_warnings":
        notes.append("The primary semantic pass completed, but one council route returned a warning.")

    if actions or consensus_value == "BLOCK" or intelligence_verdict == "BLOCK" or semantic_verdict == "BLOCK":
        return ReviewVerdict(
            "REQUEST_CHANGES",
            0.92,
            "Blocking evidence, semantic risk, review-intelligence risk, or a required action remains unanswered.",
            actions,
            notes,
        )
    if consensus_value == "NEEDS WORK" or intelligence_verdict == "NEEDS WORK" or semantic_verdict == "NEEDS WORK":
        return ReviewVerdict(
            "COMMENT",
            0.8,
            "Independent evidence sources found non-blocking concerns that should be considered before merge.",
            actions,
            notes,
        )

    challenge_confidence = float(challenge.get("confidence_after_challenge", 0.8))
    semantic_confidence = float(semantic.get("confidence", challenge_confidence))
    confidence = min(challenge_confidence, semantic_confidence) if semantic.get("status", "").startswith("completed") else challenge_confidence
    return ReviewVerdict(
        "APPROVE",
        confidence,
        "Repository evidence, capability analysis, review intelligence, semantic review, standard checks, diff review, challenge mode, and consensus are satisfied.",
        notes=notes,
    )


def _semantic_consensus_source(semantic: dict[str, Any]) -> dict[str, Any] | None:
    status = semantic.get("status")
    if status in {"completed", "completed_with_warnings"}:
        return {
            "source": "semantic-llm-review",
            "verdict": semantic.get("verdict"),
            "evidence": semantic.get("findings", []),
        }
    if semantic.get("policy") == "required" and status in {"unavailable", "error"}:
        return {
            "source": "semantic-llm-review",
            "verdict": "NEEDS WORK",
            "evidence": [semantic.get("reason", "Required semantic review did not complete.")],
        }
    return None


def run_independent_pr_review(
    root: str | Path = ".",
    *,
    changed_files: list[str] | None = None,
    external_review_file: str | Path | None = None,
) -> dict[str, Any]:
    root_path = Path(root)
    changed = changed_files or []
    semantic_files = semantic_review_files(root_path, changed)
    repository_review = review_repository(root_path)
    diff = normalize_diff_review(review_changed_files(changed), root_path, changed)
    standard = run_standard_engine(root_path, changed)
    capabilities = normalize_capability_review(run_capability_engine(root_path, changed), root_path)
    intelligence = run_review_intelligence({"capability_review": capabilities})
    challenge = run_challenge_mode(repository_review)

    semantic_context = {
        "review_scope": {
            "changed_files": changed,
            "semantic_files": semantic_files,
            "workspace_sample": not bool(changed),
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
    semantic = run_llm_review(root_path, semantic_files, semantic_context)

    external_workspace = {"summary": {"total": 0}, "decisions": [], "ready_for_memory": []}
    if external_review_file is not None:
        ingestion = ingest_external_review_file(external_review_file)
        external_workspace = build_decision_workspace(ingestion["comments"])

    consensus_sources = [
        {
            "source": "main-review",
            "verdict": repository_review.get("verdict", {}).get("verdict"),
            "evidence": repository_review.get("evidence", {}).get("findings", []),
        },
        {
            "source": "diff-review",
            "verdict": diff.get("verdict", {}).get("verdict"),
            "evidence": diff.get("evidence", {}).get("findings", []),
        },
        {"source": "capability-engine", "verdict": capabilities.get("verdict"), "evidence": capabilities.get("findings", [])},
        {
            "source": "review-intelligence",
            "verdict": intelligence.get("verdict"),
            "evidence": intelligence.get("ranked_findings", []),
        },
        {
            "source": "standard-engine",
            "verdict": "PASS" if standard.get("passed") else "NEEDS WORK",
            "evidence": standard.get("blockers", []),
        },
        {
            "source": "challenge-mode",
            "verdict": "PASS" if challenge.get("trusted") else "NEEDS WORK",
            "evidence": challenge.get("challenges", []),
        },
    ]
    semantic_source = _semantic_consensus_source(semantic)
    if semantic_source is not None:
        consensus_sources.append(semantic_source)
    consensus = build_consensus(consensus_sources)
    verdict = _decide(repository_review, standard, diff, intelligence, challenge, semantic, consensus)
    return {
        "verdict": verdict.to_dict(),
        "repository_review": repository_review.get("verdict", {}),
        "diff_review": diff.get("verdict", {}),
        "diff_review_policy": diff.get("policy_adjustments", []),
        "capability_review": capabilities,
        "review_intelligence": intelligence,
        "semantic_review": semantic,
        "semantic_files": semantic_files,
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
    notes = verdict.get("notes", [])
    if notes:
        lines.extend(["", "## Review notes"])
        lines.extend(f"- {note}" for note in notes)
    lines.extend(["", "## Evidence summary"])
    lines.append(f"- Repository verdict: {packet.get('repository_review', {}).get('verdict')}")
    lines.append(f"- Diff verdict: {packet.get('diff_review', {}).get('verdict')}")
    lines.append(f"- Capability verdict: {packet.get('capability_review', {}).get('verdict')}")
    lines.append(f"- Review intelligence verdict: {packet.get('review_intelligence', {}).get('verdict')}")
    lines.append(f"- Review quality score: {packet.get('review_intelligence', {}).get('quality_score')}")
    semantic = packet.get("semantic_review", {})
    route = semantic.get("route", {}) if isinstance(semantic, dict) else {}
    lines.append(f"- Semantic review status: {semantic.get('status')}")
    lines.append(f"- Semantic model: {route.get('model', 'unavailable')}")
    lines.append(f"- Semantic verdict: {semantic.get('verdict')}")
    lines.append(f"- Semantic confidence: {semantic.get('confidence')}")
    lines.append(f"- Semantic files supplied: {len(packet.get('semantic_files', []))}")
    lines.append(f"- High-risk assurance adjustments: {len(packet.get('diff_review_policy', []))}")
    lines.append(f"- Standard passed: {packet.get('standard', {}).get('passed')}")
    lines.append(f"- Challenge trusted: {packet.get('challenge', {}).get('trusted')}")
    lines.append(f"- Consensus: {packet.get('consensus', {}).get('consensus')}")

    semantic_findings = semantic.get("findings", []) if isinstance(semantic, dict) else []
    if semantic_findings:
        lines.extend(["", "## Semantic findings"])
        for finding in semantic_findings[:5]:
            lines.append(
                f"- **{finding.get('severity')} / {finding.get('category')}** "
                f"`{finding.get('path')}:{finding.get('line_start')}-{finding.get('line_end')}`: "
                f"{finding.get('message')}"
            )
            lines.append(f"  - Evidence: {finding.get('evidence')}")
            lines.append(f"  - Why it matters: {finding.get('why_it_matters')}")
            lines.append(f"  - Safer alternative: {finding.get('safer_alternative')}")

    assurance = packet.get("diff_review_policy", [])
    if assurance:
        lines.extend(["", "## High-risk change assurance"])
        for adjustment in assurance:
            lines.append(
                f"- `{adjustment.get('path')}` reviewed in `{adjustment.get('assurance_document')}`: "
                f"{adjustment.get('reason')}"
            )

    capability_status = packet.get("capability_review", {}).get("capability_status", {})
    if capability_status:
        lines.extend(["", "## Tier 1 capabilities"])
        for name, status in capability_status.items():
            lines.append(f"- {name}: {status}")
    ranked = packet.get("review_intelligence", {}).get("ranked_findings", [])
    if ranked:
        lines.extend(["", "## Tier 2 ranked findings"])
        for finding in ranked[:5]:
            lines.append(f"- **{finding.get('severity')} / {finding.get('root_cause')}**: {finding.get('message')}")
            lines.append(f"  - Why it matters: {finding.get('why_it_matters')}")
            lines.append(f"  - Safer alternative: {finding.get('safer_alternative')}")
    lines.extend(["", "## Rule"])
    lines.append(
        "Sergeant is the reviewer. Main Review is the reviewer core. Deterministic evidence remains authoritative; provider-routed LLMs are independent, evidence-validated review sources. External reviewer comments are optional learning inputs, not required gates."
    )
    return "\n".join(lines) + "\n"
