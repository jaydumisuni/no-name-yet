"""Workspace-ready Cpl campaign planning and replay.

Cpl receives the current ground picture, authorizes specialist work through
permanent officers, and prepares bounded workspace/research requests.  The
module does not claim that Ptah facilities are connected; requests remain
awaiting_adapter until a real adapter returns validated evidence.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Iterable

from .operational_contracts import (
    CONTRACT_VERSION,
    evidence_packet,
    mission_packet,
    research_request,
    stable_id,
    task_packet,
    validate_evidence_packet,
    workspace_request,
)

_SECURITY_MARKERS = ("auth", "security", "secret", "token", "payment", "webhook", "shell", "exec")
_RUNTIME_MARKERS = ("async", "queue", "cache", "worker", "thread", "retry", "stream", "runtime")
_CONTRACT_MARKERS = ("api", "schema", "contract", "workflow", "migration", "manifest", "package", "docs")
_MANIFEST_NAMES = {
    "pyproject.toml",
    "package.json",
    "go.mod",
    "cargo.toml",
    "build.gradle",
    "pom.xml",
    "gemfile",
    "composer.json",
    "dockerfile",
}


def _text(value: object) -> str:
    return str(value or "").strip()


def _contains_marker(text: str, marker: str) -> bool:
    normalized = marker.lower()
    if any(not char.isalnum() and char != "_" for char in normalized):
        return normalized in text
    return re.search(rf"(?<![a-z0-9_]){re.escape(normalized)}(?![a-z0-9_])", text) is not None


def _contains_any_marker(text: str, markers: Iterable[str]) -> bool:
    return any(_contains_marker(text, marker) for marker in markers)


def _work_size(changed_files: list[str], *, risk_boost: int = 0) -> int:
    return max(2, min(12, math.ceil(max(1, len(changed_files)) / 3) + risk_boost))


def _scope_text(changed_files: Iterable[str], findings: Iterable[dict[str, Any]]) -> str:
    rows = [str(item).lower() for item in changed_files]
    rows.extend(
        " ".join(
            _text(item.get(key)).lower()
            for key in ("root_cause", "category", "message", "path")
        )
        for item in findings
    )
    return "\n".join(rows)


def _hypotheses(
    mission_id: str,
    admitted: list[dict[str, Any]],
    advisory: list[dict[str, Any]],
    assurances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for finding in admitted:
        statement = _text(finding.get("message") or finding.get("root_cause"))
        rows.append({
            "hypothesis_id": stable_id("hypothesis", mission_id, finding.get("finding_id"), statement),
            "statement": statement,
            "owner_officer": _text(finding.get("officer") or "Analyst"),
            "status": "supported",
            "priority": "verdict_affecting",
            "supporting_evidence": [_text(finding.get("evidence_ref"))] if finding.get("evidence_ref") else [],
            "falsifier": "Produce grounded execution, contract, or test evidence showing the claimed path is unreachable or already protected.",
            "source_finding_id": finding.get("finding_id"),
        })
    for item in assurances:
        if item.get("status") == "satisfied":
            continue
        statement = f"Required assurance remains unresolved: {_text(item.get('required_assurance'))}"
        rows.append({
            "hypothesis_id": stable_id("hypothesis", mission_id, item.get("assurance_id"), statement),
            "statement": statement,
            "owner_officer": "Judge",
            "status": "unresolved",
            "priority": "verdict_affecting" if item.get("gates_verdict") else "confidence_only",
            "supporting_evidence": [_text(item.get("evidence"))] if item.get("evidence") else [],
            "falsifier": "Supply the exact required proof and allow Judge to reclassify the assurance as satisfied.",
            "source_assurance_id": item.get("assurance_id"),
        })
    if not rows:
        rows.append({
            "hypothesis_id": stable_id("hypothesis", mission_id, "clean-change"),
            "statement": "No actionable defect remains in the authorized changed scope.",
            "owner_officer": "Challenger",
            "status": "provisional",
            "priority": "clean-pass-challenge",
            "supporting_evidence": [],
            "falsifier": "Produce one grounded counterexample from the authorized scope that survives officer and Judge review.",
        })
    for item in advisory:
        if item.get("admission") not in {"advisory", "risk_trigger"}:
            continue
        rows.append({
            "hypothesis_id": stable_id("hypothesis", mission_id, item.get("finding_id"), "advisory"),
            "statement": _text(item.get("message")),
            "owner_officer": _text(item.get("officer") or "Analyst"),
            "status": "informational",
            "priority": "non_gating",
            "supporting_evidence": [_text(item.get("evidence_ref"))] if item.get("evidence_ref") else [],
            "falsifier": "Not required for the current verdict; re-evaluate if new grounded impact evidence appears.",
            "source_finding_id": item.get("finding_id"),
        })
    return rows


def _field_tasks(
    mission_id: str,
    changed_files: list[str],
    findings: list[dict[str, Any]],
    assurances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    text = _scope_text(changed_files, findings)
    tasks: list[dict[str, Any]] = []
    scout = task_packet(
        mission_id=mission_id,
        officer="Scout",
        objective="Map the changed battlefield, callers, dependencies, tests, documentation, and risk boundaries.",
        scope=changed_files,
        questions=("Which files and contracts changed?", "Which callers, tests, and documentation are affected?"),
        required_evidence=("exact path and line", "dependency or caller reference", "test/documentation reference"),
        allowed_capabilities=("repository_reader", "call_graph", "test_mapper", "documentation_mapper"),
        human_equivalent_workers=_work_size(changed_files),
    )
    tasks.append(scout)

    tasks.append(task_packet(
        mission_id=mission_id,
        officer="Engineer",
        objective="Establish implementation correctness, architecture, contracts, lifecycle, and cross-file consequences.",
        scope=changed_files,
        questions=("Do implementation and declared contracts agree?", "Can state or lifecycle become inconsistent?"),
        required_evidence=("source-to-sink or call-chain trace", "contract comparison", "clean counterexample"),
        allowed_capabilities=("repository_reader", "call_graph", "contract_comparator", "test_inspector"),
        human_equivalent_workers=_work_size(changed_files, risk_boost=1 if findings else 0),
        dependencies=(scout["task_id"],),
    ))

    if _contains_any_marker(text, _SECURITY_MARKERS) or any(item.get("gates_verdict") for item in assurances):
        tasks.append(task_packet(
            mission_id=mission_id,
            officer="Medic",
            objective="Trace trust boundaries, diagnose confirmed risks, and define safe repair, rollback, and regression proof.",
            scope=changed_files,
            questions=("Can hostile or unauthorized input reach a privileged sink?", "What is the safest repair and rollback sequence?"),
            required_evidence=("trust-boundary trace", "reachable abuse path or falsifier", "repair and rollback proof"),
            allowed_capabilities=("security_scanner", "repository_reader", "runtime_reproducer", "test_runner"),
            human_equivalent_workers=_work_size(changed_files, risk_boost=2),
            dependencies=(scout["task_id"],),
        ))

    if _contains_any_marker(text, _RUNTIME_MARKERS):
        tasks.append(task_packet(
            mission_id=mission_id,
            officer="Mechanic",
            objective="Inspect runtime ordering, retries, concurrency, resource lifetime, and performance worlds.",
            scope=changed_files,
            questions=("Can timing or retries change the result?", "What happens under concurrency, failure, restart, or rollback?"),
            required_evidence=("temporal execution trace", "concurrency or retry counterexample", "resource/performance measurement"),
            allowed_capabilities=("runtime_tracer", "test_runner", "benchmark_runner", "repository_reader"),
            human_equivalent_workers=_work_size(changed_files, risk_boost=1),
            dependencies=(scout["task_id"],),
        ))

    tasks.append(task_packet(
        mission_id=mission_id,
        officer="Challenger",
        objective="Attempt to disprove the preferred conclusion and expose hidden assumptions, bypasses, or false confidence.",
        scope=changed_files,
        questions=("What evidence would make the current conclusion false?", "Which important world or counterexample was not inspected?"),
        required_evidence=("explicit falsifier", "counterexample or failed attack", "unanswered assumption list"),
        allowed_capabilities=("repository_reader", "test_runner", "runtime_reproducer", "research_lookup"),
        human_equivalent_workers=_work_size(changed_files, risk_boost=1),
        dependencies=tuple(item["task_id"] for item in tasks),
    ))
    return tasks


def _synthesis_tasks(mission_id: str, changed_files: list[str], field_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dependencies = tuple(item["task_id"] for item in field_tasks)
    return [
        task_packet(
            mission_id=mission_id,
            officer="Analyst",
            objective="Reconcile duplicate claims, root causes, competing explanations, and unresolved contradictions.",
            scope=changed_files,
            questions=("Which reports describe the same root cause?", "Which contradictions remain material?"),
            required_evidence=("canonical root-cause map", "preserved dissent", "fact/assumption separation"),
            allowed_capabilities=("evidence_ledger", "root_cause_reconciler"),
            dependencies=dependencies,
            execution_mode="officer",
        ),
        task_packet(
            mission_id=mission_id,
            officer="Judge",
            objective="Adjudicate evidence strength and recommend whether the proof threshold is satisfied.",
            scope=changed_files,
            questions=("Which claims survive grounding and challenge?", "Does any required assurance remain unresolved?"),
            required_evidence=("admission ledger", "evidence-strength comparison", "unresolved-objection audit"),
            allowed_capabilities=("evidence_ledger", "assurance_policy"),
            dependencies=dependencies,
            execution_mode="officer",
        ),
        task_packet(
            mission_id=mission_id,
            officer="Archivist",
            objective="Preserve the replayable audit, provenance, dissent, and verified lesson candidates.",
            scope=changed_files,
            questions=("Can every conclusion be traced to source evidence?", "Which lessons are eligible for verified memory?"),
            required_evidence=("transaction ledger", "provenance chain", "lesson-candidate boundary"),
            allowed_capabilities=("artifact_store", "provenance_recorder", "memory_candidate_writer"),
            dependencies=dependencies,
            execution_mode="officer",
        ),
    ]


def _workspace_requests(mission_id: str, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task in tasks:
        capabilities = set(task.get("allowed_capabilities", []))
        facility = "repository"
        action = "inspect_authorized_scope"
        artifacts = ["structured evidence packet", "tool provenance"]
        if "runtime_tracer" in capabilities or "runtime_reproducer" in capabilities:
            facility, action = "runtime", "reproduce_bounded_execution_world"
            artifacts.extend(["runtime trace", "environment manifest"])
        elif "test_runner" in capabilities:
            facility, action = "test", "run_bounded_regression_or_reproduction"
            artifacts.extend(["test log", "exit status"])
        elif task.get("execution_mode") == "officer":
            continue
        rows.append(workspace_request(
            mission_id=mission_id,
            task_id=task["task_id"],
            facility=facility,
            action=action,
            scope=task.get("scope", []),
            required_artifacts=artifacts,
        ))
    return rows


def _research_requests(mission_id: str, tasks: list[dict[str, Any]], changed_files: list[str], cpl: dict[str, Any]) -> list[dict[str, Any]]:
    text = "\n".join(changed_files).lower()
    requires_current_lookup = any(Path(path).name.lower() in _MANIFEST_NAMES for path in changed_files)
    requires_current_lookup = requires_current_lookup or _contains_any_marker(text, _CONTRACT_MARKERS)
    requires_current_lookup = requires_current_lookup or bool(cpl.get("final_gaps") or cpl.get("council", {}).get("final_gaps"))
    if not requires_current_lookup:
        return []
    scout = next((item for item in tasks if item.get("responsible_officer") == "Scout"), None)
    if scout is None:
        return []
    return [research_request(
        mission_id=mission_id,
        task_id=scout["task_id"],
        question="Retrieve current official documentation, repository history, and security advisories needed to validate the changed contracts; return only claims relevant to the authorized scope.",
        allowed_sources=("official_documentation", "canonical_repository", "security_advisory"),
        freshness="current_at_retrieval",
        privacy="public_metadata_only",
    )]


def build_cpl_campaign(
    root: str | Path,
    changed_files: Iterable[str],
    *,
    officer_reports: list[dict[str, Any]],
    admitted: list[dict[str, Any]],
    advisory: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    assurances: list[dict[str, Any]],
    cpl: dict[str, Any],
    offline: dict[str, Any],
) -> dict[str, Any]:
    changed = sorted({str(item) for item in changed_files if str(item)})
    mission = mission_packet(
        objective="Establish whether the changed engineering state is safe, explain the actual root causes, and define any required proof or repair obligations.",
        scope=changed,
        constraints=(
            "evidence before conclusions",
            "do not expand scope without officer and Cpl authorization",
            "models and facilities cannot acquire rank or verdict authority",
            "private evidence must return through the responsible officer",
            "Sergeant remains the final engineering authority",
        ),
        required_proof=(
            "repository-grounded evidence",
            "important alternatives and falsifiers checked",
            "root causes reconciled",
            "required assurance satisfied or disclosed",
            "complete provenance and transaction history",
        ),
    )
    hypotheses = _hypotheses(mission["mission_id"], admitted, advisory, assurances)
    field_tasks = _field_tasks(mission["mission_id"], changed, [*admitted, *advisory], assurances)
    synthesis_tasks = _synthesis_tasks(mission["mission_id"], changed, field_tasks)
    tasks = [*field_tasks, *synthesis_tasks]
    workspace_requests = _workspace_requests(mission["mission_id"], tasks)
    research_requests = _research_requests(mission["mission_id"], tasks, changed, cpl)
    private_tasks = [item for item in tasks if item.get("execution_mode") == "private_cell"]
    private_total = sum(int(item.get("budget", {}).get("private_count") or 0) for item in private_tasks)
    unresolved_assurances = [item for item in assurances if item.get("gates_verdict") and item.get("status") != "satisfied"]
    model_passes = list(cpl.get("passes", []))
    council_round = {
        "round_number": 1,
        "ground_picture": {
            "changed_files": changed,
            "deterministic_findings": len(admitted),
            "advisory_findings": len(advisory),
            "rejected_findings": len(rejected),
            "unresolved_assurances": len(unresolved_assurances),
            "model_support_status": cpl.get("status", "not_deployed"),
            "model_passes": len(model_passes),
            "offline_investigation_complete": bool(offline.get("complete", True)),
        },
        "decisions": [
            f"Authorize {len(private_tasks)} differentiated private-cell task(s) under permanent officers.",
            "Keep workspace and research requests awaiting a real governed adapter.",
            "Require new questions to return for officer/Cpl authorization before another cell is created.",
        ],
        "authorized_tasks": [item["task_id"] for item in tasks],
        "pending_authorizations": [],
        "evidence_saturation": not unresolved_assurances,
        "report_ready_for_sergeant": not unresolved_assurances,
    }
    transactions = [
        {
            "transaction": "campaign_prepared",
            "sender": "Cpl",
            "recipient": "permanent_officers",
            "mission_id": mission["mission_id"],
            "task_count": len(tasks),
            "planned_private_count": private_total,
        },
        *(
            {
                "transaction": "task_authorized",
                "sender": "Cpl",
                "recipient": item["responsible_officer"],
                "mission_id": mission["mission_id"],
                "task_id": item["task_id"],
                "private_count": item.get("budget", {}).get("private_count", 0),
            }
            for item in tasks
        ),
        *(
            {
                "transaction": "request_waiting_for_adapter",
                "sender": item.get("responsible_officer") or "Cpl",
                "recipient": "Ptah/Hunter Workspace",
                "request_id": item["request_id"],
                "task_id": item["task_id"],
            }
            for item in workspace_requests
        ),
        *(
            {
                "transaction": "research_waiting_for_adapter",
                "sender": "Scout",
                "recipient": "governed_research_facility",
                "request_id": item["request_id"],
                "task_id": item["task_id"],
            }
            for item in research_requests
        ),
    ]
    return {
        "schema_version": "sergeant.cpl-campaign.v1",
        "contract_version": CONTRACT_VERSION,
        "status": "prepared",
        "mission": mission,
        "hypotheses": hypotheses,
        "tasks": tasks,
        "workspace_requests": workspace_requests,
        "research_requests": research_requests,
        "council_rounds": [council_round],
        "pending_authorizations": [],
        "evidence_packets": [],
        "assurance_gates": [dict(item) for item in assurances],
        "private_force": {
            "multiplier": 10,
            "minimum_private_count": 20,
            "private_cell_tasks": len(private_tasks),
            "planned_private_count": private_total,
            "rule": "Normally justified workers × 10, with twenty as the minimum private formation.",
        },
        "adapter_status": {
            "workspace": "awaiting_adapter",
            "research": "awaiting_adapter" if research_requests else "not_required",
        },
        "model_support": {
            "status": cpl.get("status", "not_deployed"),
            "passes": len(model_passes),
            "rule": "Models amplify officer packets; they do not create the council or issue Sergeant's verdict.",
        },
        "report_ready_for_sergeant": not unresolved_assurances,
        "transactions": transactions,
    }


def advance_campaign(campaign: dict[str, Any], evidence_packets: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Create the next council round from validated evidence without auto-spawning work.

    New evidence cannot silently clear a prior required-assurance gate.  A gate
    must be explicitly adjudicated to ``satisfied`` in ``assurance_gates`` before
    the campaign becomes report-ready.
    """

    updated = dict(campaign)
    tasks = {item["task_id"]: dict(item) for item in campaign.get("tasks", [])}
    accepted = list(campaign.get("evidence_packets", []))
    pending = list(campaign.get("pending_authorizations", []))
    evidence_refs: list[str] = []
    questions: list[str] = []
    for raw in evidence_packets:
        task = tasks.get(raw.get("task_id"))
        if task is None:
            raise ValueError("evidence references an unknown campaign task")
        packet = validate_evidence_packet(dict(raw), task)
        accepted.append(packet)
        evidence_refs.extend(str(item) for item in packet.get("evidence_refs", []))
        for question in packet.get("questions_for_officer", []):
            request = {
                "authorization_id": stable_id(
                    "authorization",
                    campaign.get("mission", {}).get("mission_id"),
                    task["task_id"],
                    question,
                ),
                "mission_id": campaign.get("mission", {}).get("mission_id"),
                "parent_task_id": task["task_id"],
                "requested_by": packet.get("worker_id"),
                "responsible_officer": task.get("responsible_officer"),
                "question": str(question),
                "recommended_human_equivalent_workers": 2,
                "recommended_private_count": 20,
                "status": "pending_officer_and_cpl_authorization",
            }
            if request["authorization_id"] not in {item.get("authorization_id") for item in pending}:
                pending.append(request)
                questions.append(str(question))

    unresolved_assurances = [
        item
        for item in campaign.get("assurance_gates", [])
        if item.get("gates_verdict") and item.get("status") != "satisfied"
    ]
    report_ready = not pending and not unresolved_assurances
    rounds = list(campaign.get("council_rounds", []))
    rounds.append({
        "round_number": len(rounds) + 1,
        "ground_picture": {
            "new_evidence_packets": len(accepted) - len(campaign.get("evidence_packets", [])),
            "new_evidence_refs": sorted(set(evidence_refs)),
            "new_questions": questions,
            "unresolved_required_assurances": len(unresolved_assurances),
        },
        "decisions": [
            "Route validated evidence to the responsible officers.",
            "Keep discovered questions pending until officer relevance and Cpl priority are authorized.",
            "Preserve prior required-assurance gates until explicit adjudication marks them satisfied.",
        ],
        "authorized_tasks": [],
        "pending_authorizations": [item["authorization_id"] for item in pending],
        "evidence_saturation": report_ready,
        "report_ready_for_sergeant": report_ready,
    })
    updated["evidence_packets"] = accepted
    updated["pending_authorizations"] = pending
    updated["council_rounds"] = rounds
    updated["report_ready_for_sergeant"] = report_ready
    updated["status"] = "evidence_received" if accepted else campaign.get("status", "prepared")
    return updated

