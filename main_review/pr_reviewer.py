"""Independent PR reviewer for Sergeant."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .capability_engine import run_capability_engine
from .capability_policy import normalize_capability_review
from .challenge import run_challenge_mode
from .consensus import build_consensus
from .cpl_noise import reconcile_cpl_findings
from .cpl_runtime import run_cpl_review
from .decision_workspace import build_decision_workspace
from .diff_policy import normalize_diff_review
from .diff_review import review_changed_files
from .officer_council import run_officer_council
from .review_ingestion import ingest_external_review_file
from .review_intelligence import run_review_intelligence
from .review_scope import scope_repository_review
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
    cpl: dict[str, Any],
    officer_council: dict[str, Any] | None = None,
) -> list[str]:
    if officer_council is not None:
        actions = [str(item) for item in officer_council.get("required_actions", []) if str(item)]
        if cpl.get("policy") == "required" and cpl.get("status") in {"unavailable", "disabled", "error"}:
            actions.append("Configure a reachable Cpl model-support route and rerun Sergeant.")
        return sorted(set(actions))

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
        for finding in intelligence.get("promoted_findings", intelligence.get("ranked_findings", [])):
            if finding.get("severity") in {"blocker", "major"}:
                actions.append(f"Answer {finding.get('root_cause')} finding: {finding.get('message')}")

    if cpl.get("policy") == "required" and cpl.get("status") in {"unavailable", "error"}:
        actions.append("Configure a reachable Cpl reasoning route and rerun Sergeant.")
    if cpl.get("decision_verdict", cpl.get("verdict")) in {"BLOCK", "NEEDS WORK"}:
        for finding in cpl.get("actionable_findings", cpl.get("findings", [])):
            if finding.get("severity") in {"blocker", "major"}:
                location = f"{finding.get('path')}:{finding.get('line_start')}-{finding.get('line_end')}"
                actions.append(f"Answer Cpl {finding.get('severity')} finding at {location}: {finding.get('message')}")
    return sorted(set(action for action in actions if action))


def _decide(
    repository_review: dict[str, Any],
    standard: dict[str, Any],
    diff: dict[str, Any],
    intelligence: dict[str, Any],
    challenge: dict[str, Any],
    cpl: dict[str, Any],
    consensus: dict[str, Any],
    officer_council: dict[str, Any] | None = None,
) -> ReviewVerdict:
    actions = _required_actions(repository_review, standard, diff, intelligence, cpl, officer_council)
    consensus_value = consensus.get("consensus")
    intelligence_verdict = intelligence.get("verdict")
    cpl_verdict = cpl.get("decision_verdict", cpl.get("verdict"))
    notes = ["External reviewer comments are optional learning inputs, not required gates."]
    if cpl.get("status") in {"unavailable", "disabled", "error"} and cpl.get("policy") != "required":
        if officer_council is not None:
            notes.append("Model support was not available; Cpl still completed the deterministic permanent-officer formation.")
        else:
            notes.append("Cpl reasoning was not available; deterministic Sergeant evidence remained authoritative.")
    if cpl.get("status") == "completed_with_warnings":
        notes.append("Cpl completed with one or more council or officer-support warnings.")
    council_state = cpl.get("council", {})
    if council_state.get("mode") not in {None, "not_deployed"} and council_state.get("complete") is False:
        notes.append("Cpl preserved unresolved council gaps for Sergeant instead of inventing certainty.")

    if officer_council is not None:
        formation_verdict = officer_council.get("verdict", "PASS")
        if actions or formation_verdict in {"BLOCK", "NEEDS WORK"}:
            return ReviewVerdict(
                "REQUEST_CHANGES",
                0.94 if formation_verdict == "BLOCK" else 0.9,
                "The permanent-officer formation admitted actionable evidence or an explicit required-assurance obligation remains unresolved.",
                actions,
                notes,
            )
        return ReviewVerdict(
            "APPROVE",
            0.88,
            "The deterministic permanent-officer formation completed, Judge admitted no actionable defects, and all explicit assurance obligations were satisfied.",
            notes=notes,
        )

    if actions or consensus_value == "BLOCK" or intelligence_verdict == "BLOCK" or cpl_verdict == "BLOCK":
        return ReviewVerdict(
            "REQUEST_CHANGES",
            0.92,
            "Blocking evidence, Cpl council risk, review-intelligence risk, or a required action remains unanswered.",
            actions,
            notes,
        )
    if consensus_value == "NEEDS WORK" or intelligence_verdict == "NEEDS WORK" or cpl_verdict == "NEEDS WORK":
        return ReviewVerdict(
            "COMMENT",
            0.8,
            "Independent evidence sources found non-blocking concerns that should be considered before merge.",
            actions,
            notes,
        )

    challenge_confidence = float(challenge.get("confidence_after_challenge", 0.8))
    cpl_confidence = float(cpl.get("confidence", challenge_confidence))
    confidence = min(challenge_confidence, cpl_confidence) if cpl.get("status", "").startswith("completed") else challenge_confidence
    return ReviewVerdict(
        "APPROVE",
        confidence,
        "Repository evidence, capability analysis, review intelligence, Cpl council reasoning, standard checks, diff review, challenge mode, and consensus are satisfied.",
        notes=notes,
    )


def _cpl_consensus_source(cpl: dict[str, Any]) -> dict[str, Any] | None:
    status = cpl.get("status")
    if status in {"completed", "completed_with_warnings"}:
        return {
            "source": "cpl-reasoning",
            "verdict": cpl.get("decision_verdict", cpl.get("verdict")),
            "evidence": cpl.get("decision_findings", cpl.get("findings", [])),
        }
    if cpl.get("policy") == "required" and status in {"unavailable", "error"}:
        return {
            "source": "cpl-reasoning",
            "verdict": "NEEDS WORK",
            "evidence": [cpl.get("reason", "Required Cpl reasoning did not complete.")],
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
    raw_repository_review = review_repository(root_path)
    repository_review = scope_repository_review(raw_repository_review, changed)
    diff = normalize_diff_review(review_changed_files(changed), root_path, changed)
    standard = run_standard_engine(root_path, changed)
    capabilities = normalize_capability_review(run_capability_engine(root_path, changed), root_path)
    intelligence = run_review_intelligence({"capability_review": capabilities})
    challenge = run_challenge_mode(repository_review)

    cpl_context = {
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
    cpl = {
        **cpl,
        "coordination_status": "completed",
        "officer_formation": officer_council,
    }

    external_workspace = {"summary": {"total": 0}, "decisions": [], "ready_for_memory": []}
    if external_review_file is not None:
        ingestion = ingest_external_review_file(external_review_file)
        external_workspace = build_decision_workspace(ingestion["comments"])

    # Raw scanners, diff risk signals and model responses are evidence inputs,
    # not independent votes.  The canonical officer ledger is the one source
    # presented to Sergeant after Analyst, Challenger and Judge adjudication.
    consensus_sources = [{
        "source": "officer-council",
        "verdict": officer_council.get("verdict"),
        "evidence": officer_council.get("admitted_findings", []),
    }]
    consensus = build_consensus(consensus_sources)
    verdict = _decide(repository_review, standard, diff, intelligence, challenge, cpl, consensus, officer_council)
    return {
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
    quality = packet.get("review_intelligence", {}).get("quality_score")
    quality_text = f"{quality}/100 review-output completeness" if quality is not None else "not evaluated (no ranked findings)"
    lines.append(f"- Review quality score: {quality_text}")
    scope = packet.get("repository_review_scope", {})
    if scope:
        lines.append(f"- Repository findings in changed scope: {scope.get('scoped_finding_count', 0)}")
        lines.append(f"- Repository background findings: {scope.get('background_finding_count', 0)}")
    cpl = packet.get("cpl_review", packet.get("semantic_review", {}))
    route = cpl.get("route", {}) if isinstance(cpl, dict) else {}
    council = cpl.get("council", {}) if isinstance(cpl, dict) else {}
    lines.append(f"- Cpl status: {cpl.get('status')}")
    lines.append(f"- Cpl role: {cpl.get('role', 'Corporal Specialist')}")
    lines.append(f"- Cpl depth: {cpl.get('depth')}")
    lines.append(f"- Cpl model: {route.get('model', 'unavailable')}")
    lines.append(f"- Cpl raw verdict: {cpl.get('verdict')}")
    lines.append(f"- Cpl decision verdict: {cpl.get('decision_verdict', cpl.get('verdict'))}")
    lines.append(f"- Cpl confidence: {cpl.get('confidence')}")
    lines.append(f"- Cpl specialist passes: {len(cpl.get('passes', []))}")
    lines.append(f"- Cpl council members: {council.get('member_count', 0)}")
    lines.append(f"- Cpl council rounds: {council.get('round_count', 0)}")
    lines.append(f"- Cpl memory checked: {cpl.get('memory_checked', False)}")
    lines.append(f"- Cpl council complete: {council.get('complete', False)}")
    formation = packet.get("officer_council", {})
    lines.append(f"- Deterministic officer formation: {formation.get('mode', 'not available')}")
    lines.append(f"- Permanent officer reports: {len(formation.get('reports', []))}")
    lines.append(f"- Admitted officer findings: {len(formation.get('admitted_findings', []))}")
    lines.append(f"- Unresolved explicit assurances: {len(formation.get('unresolved_assurances', []))}")
    campaign = formation.get("campaign", {}) if isinstance(formation, dict) else {}
    private_force = campaign.get("private_force", {}) if isinstance(campaign, dict) else {}
    adapter_status = campaign.get("adapter_status", {}) if isinstance(campaign, dict) else {}
    lines.append(f"- Cpl campaign status: {campaign.get('status', 'not prepared')}")
    lines.append(f"- Authorized operational tasks: {len(campaign.get('tasks', []))}")
    lines.append(f"- Planned private force: {private_force.get('planned_private_count', 0)}")
    lines.append(f"- Workspace adapter: {adapter_status.get('workspace', 'not prepared')}")
    lines.append(f"- Research adapter: {adapter_status.get('research', 'not prepared')}")
    lines.append(f"- Semantic files supplied: {len(packet.get('semantic_files', []))}")
    lines.append(f"- High-risk assurance adjustments: {len(packet.get('diff_review_policy', []))}")
    lines.append(f"- Standard passed: {packet.get('standard', {}).get('passed')}")
    lines.append(f"- Challenge trusted: {packet.get('challenge', {}).get('trusted')}")
    lines.append(f"- Consensus: {packet.get('consensus', {}).get('consensus')}")

    cpl_findings = cpl.get("actionable_findings", cpl.get("findings", [])) if isinstance(cpl, dict) else []
    if cpl_findings:
        lines.extend(["", "## Cpl findings"])
        for finding in cpl_findings[:5]:
            lines.append(
                f"- **{finding.get('severity')} / {finding.get('category')}** "
                f"`{finding.get('path')}:{finding.get('line_start')}-{finding.get('line_end')}`: "
                f"{finding.get('message')}"
            )
            lines.append(f"  - Evidence: {finding.get('evidence')}")
            lines.append(f"  - Why it matters: {finding.get('why_it_matters')}")
            lines.append(f"  - Safer alternative: {finding.get('safer_alternative')}")
            lines.append(f"  - Specialists: {', '.join(finding.get('supporting_specialists', []))}")

    officer_findings = formation.get("admitted_findings", []) if isinstance(formation, dict) else []
    if officer_findings:
        lines.extend(["", "## Permanent-officer findings"])
        for finding in officer_findings[:10]:
            lines.append(
                f"- **{finding.get('officer')} — {finding.get('severity')} / {finding.get('root_cause')}** "
                f"`{finding.get('evidence_ref')}`: {finding.get('message')}"
            )
            lines.append(f"  - Evidence: {finding.get('evidence')}")
            falsifiers = finding.get("falsifiers_checked", [])
            if falsifiers:
                lines.append(f"  - Falsifiers checked: {'; '.join(falsifiers)}")

    unresolved_assurances = formation.get("unresolved_assurances", []) if isinstance(formation, dict) else []
    if unresolved_assurances:
        lines.extend(["", "## Unresolved required assurance"])
        for assurance_item in unresolved_assurances:
            lines.append(
                f"- `{assurance_item.get('path') or assurance_item.get('kind')}` requires "
                f"`{assurance_item.get('required_assurance')}`: {assurance_item.get('evidence')}"
            )

    plan = cpl.get("reasoning_plan", []) if isinstance(cpl, dict) else []
    if plan:
        lines.extend(["", "## Cpl specialist plan"])
        for assignment in plan:
            lines.append(f"- **{assignment.get('title')}** using `{assignment.get('model')}`: {assignment.get('mission')}")

    rounds = council.get("rounds", []) if isinstance(council, dict) else []
    if rounds:
        lines.extend(["", "## Cpl council rounds"])
        for round_item in rounds:
            recruitment = round_item.get("recruitment", {})
            lines.append(
                f"- Round {round_item.get('round')}: recruited `{recruitment.get('model')}` "
                f"for {recruitment.get('required_capability')} because {recruitment.get('reason')}"
            )
            for command in round_item.get("instructions", []):
                lines.append(f"  - To {command.get('to_officer')}: {command.get('instruction')}")

    recurrences = cpl.get("recurrences", []) if isinstance(cpl, dict) else []
    if recurrences:
        lines.extend(["", "## Recurrence review"])
        for recurrence in recurrences:
            lines.append(f"- `{recurrence.get('previous_event_id')}` may have recurred: {recurrence.get('current_finding')}")
            lines.append(f"  - Required response: {recurrence.get('required_response')}")

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
        "Sergeant is the reviewer. Main Review is the reviewer core. Cpl is the council-led Corporal Specialist. Permanent officers own their specialties; models and gateways are replaceable engines beneath Cpl; deterministic evidence remains authoritative. External reviewer comments are optional learning inputs, not required gates."
    )
    return "\n".join(lines) + "\n"
