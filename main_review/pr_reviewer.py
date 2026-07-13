"""Independent PR reviewer for Sergeant."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .capability_engine import run_capability_engine
from .capability_policy import normalize_capability_review
from .challenge import run_challenge_mode
from .consensus import build_consensus
from .cpl_runtime import run_cpl_review
from .decision_workspace import build_decision_workspace
from .diff_policy import normalize_diff_review
from .diff_review import review_changed_files
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


def _required_actions(repository_review: dict[str, Any], standard: dict[str, Any], diff: dict[str, Any], intelligence: dict[str, Any], cpl: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    repo_verdict = repository_review.get("verdict", {})
    if isinstance(repo_verdict, dict) and repo_verdict.get("verdict") != "PASS":
        actions.append(str(repo_verdict.get("suggested_next_action", "Fix repository review findings.")))
    actions.extend(str(item) for item in standard.get("blockers", []))
    diff_verdict = diff.get("verdict", {}) if isinstance(diff, dict) else {}
    if isinstance(diff_verdict, dict) and diff_verdict.get("verdict") != "PASS":
        actions.append(str(diff_verdict.get("suggested_next_action", "Answer changed-file review findings.")))
    if intelligence.get("verdict") in {"BLOCK", "NEEDS WORK"}:
        for finding in intelligence.get("ranked_findings", []):
            if finding.get("severity") in {"blocker", "major"}:
                actions.append(f"Answer {finding.get('root_cause')} finding: {finding.get('message')}")
    if cpl.get("policy") == "required" and cpl.get("status") in {"unavailable", "error"}:
        actions.append("Configure a reachable Cpl reasoning route and rerun Sergeant.")
    if cpl.get("verdict") in {"BLOCK", "NEEDS WORK"}:
        for finding in cpl.get("findings", []):
            if finding.get("severity") in {"blocker", "major"}:
                location = f"{finding.get('path')}:{finding.get('line_start')}-{finding.get('line_end')}"
                actions.append(f"Answer Cpl {finding.get('severity')} finding at {location}: {finding.get('message')}")
    return sorted(set(item for item in actions if item))


def _decide(repository_review: dict[str, Any], standard: dict[str, Any], diff: dict[str, Any], intelligence: dict[str, Any], challenge: dict[str, Any], cpl: dict[str, Any], consensus: dict[str, Any]) -> ReviewVerdict:
    actions = _required_actions(repository_review, standard, diff, intelligence, cpl)
    consensus_value = consensus.get("consensus")
    intelligence_verdict = intelligence.get("verdict")
    cpl_verdict = cpl.get("verdict")
    notes = ["External reviewer comments are optional learning inputs, not required gates."]
    if cpl.get("status") in {"unavailable", "disabled"} and cpl.get("policy") != "required":
        notes.append("Cpl reasoning was not available; deterministic Sergeant evidence remained authoritative.")
    if cpl.get("status") == "completed_with_warnings":
        notes.append("Cpl completed with one or more council or officer-support warnings.")
    if cpl.get("council", {}).get("complete") is False:
        notes.append("Cpl preserved unresolved council gaps for Sergeant instead of inventing certainty.")

    if actions or consensus_value == "BLOCK" or intelligence_verdict == "BLOCK" or cpl_verdict == "BLOCK":
        return ReviewVerdict("REQUEST_CHANGES", 0.92, "Blocking evidence, Cpl council risk, review-intelligence risk, or a required action remains unanswered.", actions, notes)
    if consensus_value == "NEEDS WORK" or intelligence_verdict == "NEEDS WORK" or cpl_verdict == "NEEDS WORK":
        return ReviewVerdict("COMMENT", 0.8, "Independent evidence sources found non-blocking concerns that should be considered before merge.", actions, notes)
    challenge_confidence = float(challenge.get("confidence_after_challenge", 0.8))
    cpl_confidence = float(cpl.get("confidence", challenge_confidence))
    confidence = min(challenge_confidence, cpl_confidence) if str(cpl.get("status", "")).startswith("completed") else challenge_confidence
    return ReviewVerdict("APPROVE", confidence, "Repository evidence, capability analysis, review intelligence, Cpl council reasoning, standard checks, diff review, challenge mode, and consensus are satisfied.", notes=notes)


def _cpl_consensus_source(cpl: dict[str, Any]) -> dict[str, Any] | None:
    status = cpl.get("status")
    if status in {"completed", "completed_with_warnings"}:
        return {"source": "cpl-reasoning", "verdict": cpl.get("verdict"), "evidence": cpl.get("findings", [])}
    if cpl.get("policy") == "required" and status in {"unavailable", "error"}:
        return {"source": "cpl-reasoning", "verdict": "NEEDS WORK", "evidence": [cpl.get("reason", "Required Cpl reasoning did not complete.")]}
    return None


def run_independent_pr_review(root: str | Path = ".", *, changed_files: list[str] | None = None, external_review_file: str | Path | None = None) -> dict[str, Any]:
    root_path = Path(root)
    changed = changed_files or []
    semantic_files = semantic_review_files(root_path, changed)
    repository_review = review_repository(root_path)
    diff = normalize_diff_review(review_changed_files(changed), root_path, changed)
    standard = run_standard_engine(root_path, changed)
    capabilities = normalize_capability_review(run_capability_engine(root_path, changed), root_path)
    intelligence = run_review_intelligence({"capability_review": capabilities})
    challenge = run_challenge_mode(repository_review)
    cpl_context = {
        "review_scope": {"changed_files": changed, "semantic_files": semantic_files, "workspace_sample": not bool(changed)},
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

    external_workspace = {"summary": {"total": 0}, "decisions": [], "ready_for_memory": []}
    if external_review_file is not None:
        ingestion = ingest_external_review_file(external_review_file)
        external_workspace = build_decision_workspace(ingestion["comments"])

    sources = [
        {"source": "main-review", "verdict": repository_review.get("verdict", {}).get("verdict"), "evidence": repository_review.get("evidence", {}).get("findings", [])},
        {"source": "diff-review", "verdict": diff.get("verdict", {}).get("verdict"), "evidence": diff.get("evidence", {}).get("findings", [])},
        {"source": "capability-engine", "verdict": capabilities.get("verdict"), "evidence": capabilities.get("findings", [])},
        {"source": "review-intelligence", "verdict": intelligence.get("verdict"), "evidence": intelligence.get("ranked_findings", [])},
        {"source": "standard-engine", "verdict": "PASS" if standard.get("passed") else "NEEDS WORK", "evidence": standard.get("blockers", [])},
        {"source": "challenge-mode", "verdict": "PASS" if challenge.get("trusted") else "NEEDS WORK", "evidence": challenge.get("challenges", [])},
    ]
    cpl_source = _cpl_consensus_source(cpl)
    if cpl_source:
        sources.append(cpl_source)
    consensus = build_consensus(sources)
    verdict = _decide(repository_review, standard, diff, intelligence, challenge, cpl, consensus)
    return {
        "verdict": verdict.to_dict(),
        "repository_review": repository_review.get("verdict", {}),
        "diff_review": diff.get("verdict", {}),
        "diff_review_policy": diff.get("policy_adjustments", []),
        "capability_review": capabilities,
        "review_intelligence": intelligence,
        "cpl_review": cpl,
        "semantic_review": cpl,
        "semantic_files": semantic_files,
        "standard": standard,
        "challenge": challenge,
        "external_decisions": external_workspace,
        "consensus": consensus,
        "changed_files": changed,
    }


def render_pr_review_markdown(packet: dict[str, Any]) -> str:
    verdict = packet.get("verdict", {})
    lines = ["# Sergeant Review", "", f"Verdict: **{verdict.get('verdict', 'UNKNOWN')}**", f"Confidence: **{verdict.get('confidence', 0)}**", "", str(verdict.get("reason", ""))]
    if verdict.get("required_actions"):
        lines.extend(["", "## Required actions", *[f"- {item}" for item in verdict["required_actions"]]])
    if verdict.get("notes"):
        lines.extend(["", "## Review notes", *[f"- {item}" for item in verdict["notes"]]])
    cpl = packet.get("cpl_review", packet.get("semantic_review", {}))
    route = cpl.get("route", {}) if isinstance(cpl, dict) else {}
    council = cpl.get("council", {}) if isinstance(cpl, dict) else {}
    lines.extend([
        "", "## Evidence summary",
        f"- Repository verdict: {packet.get('repository_review', {}).get('verdict')}",
        f"- Diff verdict: {packet.get('diff_review', {}).get('verdict')}",
        f"- Capability verdict: {packet.get('capability_review', {}).get('verdict')}",
        f"- Review intelligence verdict: {packet.get('review_intelligence', {}).get('verdict')}",
        f"- Review quality score: {packet.get('review_intelligence', {}).get('quality_score')}",
        f"- Cpl status: {cpl.get('status')}",
        f"- Cpl role: {cpl.get('role', 'Corporal Specialist')}",
        f"- Cpl depth: {cpl.get('depth')}",
        f"- Cpl model: {route.get('model', 'unavailable')}",
        f"- Cpl verdict: {cpl.get('verdict')}",
        f"- Cpl confidence: {cpl.get('confidence')}",
        f"- Cpl specialist passes: {len(cpl.get('passes', []))}",
        f"- Cpl council members: {council.get('member_count', 0)}",
        f"- Cpl council rounds: {council.get('round_count', 0)}",
        f"- Cpl memory checked: {cpl.get('memory_checked', False)}",
        f"- Semantic files supplied: {len(packet.get('semantic_files', []))}",
        f"- Standard passed: {packet.get('standard', {}).get('passed')}",
        f"- Challenge trusted: {packet.get('challenge', {}).get('trusted')}",
        f"- Consensus: {packet.get('consensus', {}).get('consensus')}",
    ])
    findings = cpl.get("findings", []) if isinstance(cpl, dict) else []
    if findings:
        lines.extend(["", "## Cpl findings"])
        for finding in findings[:5]:
            lines.append(f"- **{finding.get('severity')} / {finding.get('category')}** `{finding.get('path')}:{finding.get('line_start')}-{finding.get('line_end')}`: {finding.get('message')}")
            lines.append(f"  - Evidence: {finding.get('evidence')}")
            lines.append(f"  - Why it matters: {finding.get('why_it_matters')}")
            lines.append(f"  - Safer alternative: {finding.get('safer_alternative')}")
    lines.extend(["", "## Rule", "Sergeant is the reviewer. Cpl is the council-led Corporal Specialist. Permanent officers own their specialties; models are replaceable council members; deterministic evidence remains authoritative. External reviewer comments are optional learning inputs, not required gates."])
    return "\n".join(lines) + "\n"
