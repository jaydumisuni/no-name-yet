from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dedent(content).lstrip(), encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected patch anchor missing in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


write(
    "main_review/operational_contracts.py",
    r'''
    """Versioned command, task, and evidence contracts for Cpl operations.

    These contracts exist before Ptah/Hunter Workspace.  They let Sergeant plan,
    authorize, audit, and replay work without pretending an execution facility is
    already connected.  Models and workspace tools are replaceable capabilities;
    permanent officers and Sergeant authority remain stable.
    """

    from __future__ import annotations

    import hashlib
    import json
    import re
    from typing import Any, Iterable

    CONTRACT_VERSION = "sergeant.operational-contracts.v1"
    PRIVATE_FORCE_MULTIPLIER = 10
    MINIMUM_PRIVATE_FORCE = 20
    FORBIDDEN_EVIDENCE_KEYS = {
        "verdict",
        "final_verdict",
        "approve",
        "approved",
        "block",
        "sergeant_verdict",
    }
    _SECRET_RE = re.compile(
        r"(?i)(?:api[_-]?key|authorization|bearer|password|passwd|secret|token)\s*[:=]\s*[^\s,;]+"
    )
    _LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:\\|/(?:home|root|users|private|workspace)/)", re.IGNORECASE)


    def stable_id(prefix: str, *parts: object) -> str:
        payload = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
        return f"{prefix}-" + hashlib.sha256(payload.encode()).hexdigest()[:16]


    def private_force_size(human_equivalent_workers: int) -> int:
        """Scale ordinary worker need by ten, with twenty as the minimum formation."""

        human = max(1, int(human_equivalent_workers))
        return max(MINIMUM_PRIVATE_FORCE, human * PRIVATE_FORCE_MULTIPLIER)


    def mission_packet(
        *,
        objective: str,
        scope: Iterable[str],
        constraints: Iterable[str],
        required_proof: Iterable[str],
        permissions: Iterable[str] = ("read_repository", "run_approved_tools"),
        privacy: str = "repository_scoped",
    ) -> dict[str, Any]:
        normalized_scope = sorted({str(item) for item in scope if str(item)})
        mission_id = stable_id("mission", objective, normalized_scope)
        return {
            "schema_version": CONTRACT_VERSION,
            "mission_id": mission_id,
            "issued_by": "Sergeant",
            "commanded_by": "Cpl",
            "objective": str(objective).strip(),
            "scope": normalized_scope,
            "constraints": [str(item) for item in constraints if str(item)],
            "permissions": [str(item) for item in permissions if str(item)],
            "required_proof": [str(item) for item in required_proof if str(item)],
            "privacy": privacy,
            "authority_boundary": {
                "sergeant": "defines mission, gates, required proof, and final verdict",
                "cpl": "commands the investigation campaign and council rounds",
                "officers": "own specialist doctrine and authorize bounded work",
                "privates": "execute assigned evidence obligations without changing authority",
                "models": "replaceable reasoning engines with no rank",
                "workspace": "replaceable execution facilities with no decision authority",
                "hermes": "transports and preserves; never commands or decides",
            },
        }


    def task_packet(
        *,
        mission_id: str,
        officer: str,
        objective: str,
        scope: Iterable[str],
        questions: Iterable[str],
        required_evidence: Iterable[str],
        allowed_capabilities: Iterable[str],
        human_equivalent_workers: int = 2,
        dependencies: Iterable[str] = (),
        stop_conditions: Iterable[str] = (
            "required evidence found",
            "scope exhausted",
            "missing dependency requires escalation",
        ),
        escalation_conditions: Iterable[str] = (
            "scope extension required",
            "contradictory grounded evidence",
            "required capability unavailable",
        ),
        execution_mode: str = "private_cell",
    ) -> dict[str, Any]:
        normalized_scope = sorted({str(item) for item in scope if str(item)})
        task_id = stable_id("task", mission_id, officer, objective, normalized_scope)
        private_count = private_force_size(human_equivalent_workers) if execution_mode == "private_cell" else 0
        return {
            "schema_version": CONTRACT_VERSION,
            "mission_id": mission_id,
            "task_id": task_id,
            "assigned_by": officer,
            "responsible_officer": officer,
            "objective": str(objective).strip(),
            "scope": normalized_scope,
            "questions": [str(item) for item in questions if str(item)],
            "required_evidence": [str(item) for item in required_evidence if str(item)],
            "allowed_capabilities": sorted({str(item) for item in allowed_capabilities if str(item)}),
            "dependencies": [str(item) for item in dependencies if str(item)],
            "budget": {
                "human_equivalent_workers": max(1, int(human_equivalent_workers)),
                "private_force_multiplier": PRIVATE_FORCE_MULTIPLIER,
                "private_count": private_count,
                "max_rounds": 3,
                "external_paid_calls": 0,
            },
            "stop_conditions": [str(item) for item in stop_conditions if str(item)],
            "escalation_conditions": [str(item) for item in escalation_conditions if str(item)],
            "execution_mode": execution_mode,
            "status": "authorized",
            "may_issue_verdict": False,
            "may_expand_scope": False,
            "reports_to": officer,
        }


    def workspace_request(
        *,
        mission_id: str,
        task_id: str,
        facility: str,
        action: str,
        scope: Iterable[str],
        required_artifacts: Iterable[str],
        privacy: str = "repository_scoped",
    ) -> dict[str, Any]:
        normalized_scope = sorted({str(item) for item in scope if str(item)})
        return {
            "schema_version": CONTRACT_VERSION,
            "request_id": stable_id("workspace", mission_id, task_id, facility, action, normalized_scope),
            "mission_id": mission_id,
            "task_id": task_id,
            "facility": facility,
            "action": action,
            "scope": normalized_scope,
            "required_artifacts": [str(item) for item in required_artifacts if str(item)],
            "privacy": privacy,
            "status": "awaiting_adapter",
            "authority": "authorized task only",
        }


    def research_request(
        *,
        mission_id: str,
        task_id: str,
        question: str,
        allowed_sources: Iterable[str],
        freshness: str = "current",
        privacy: str = "public_metadata_only",
    ) -> dict[str, Any]:
        clean_question = str(question).strip()
        if not clean_question:
            raise ValueError("research question is required")
        if _SECRET_RE.search(clean_question) or _LOCAL_PATH_RE.search(clean_question):
            raise ValueError("research requests cannot contain credentials or private local paths")
        sources = sorted({str(item).strip() for item in allowed_sources if str(item).strip()})
        if not sources:
            raise ValueError("research requests require an explicit source policy")
        return {
            "schema_version": CONTRACT_VERSION,
            "request_id": stable_id("research", mission_id, task_id, clean_question, sources),
            "mission_id": mission_id,
            "task_id": task_id,
            "question": clean_question,
            "allowed_sources": sources,
            "freshness": freshness,
            "privacy": privacy,
            "status": "awaiting_adapter",
            "required_provenance": ["source", "retrieved_at", "supported_claim", "freshness"],
            "authority": "evidence provider only",
        }


    def evidence_packet(
        *,
        mission_id: str,
        task_id: str,
        worker_id: str,
        claims: Iterable[dict[str, Any]],
        evidence_refs: Iterable[str],
        falsifiers_checked: Iterable[str] = (),
        uncertainty: Iterable[str] = (),
        questions_for_officer: Iterable[str] = (),
        provenance: dict[str, Any] | None = None,
        confidence: float = 0.0,
        status: str = "completed",
    ) -> dict[str, Any]:
        return {
            "schema_version": CONTRACT_VERSION,
            "mission_id": mission_id,
            "task_id": task_id,
            "worker_id": worker_id,
            "status": status,
            "claims": [dict(item) for item in claims],
            "evidence_refs": [str(item) for item in evidence_refs if str(item)],
            "falsifiers_checked": [str(item) for item in falsifiers_checked if str(item)],
            "uncertainty": [str(item) for item in uncertainty if str(item)],
            "questions_for_officer": [str(item) for item in questions_for_officer if str(item)],
            "provenance": dict(provenance or {}),
            "confidence": max(0.0, min(1.0, float(confidence))),
            "may_issue_verdict": False,
        }


    def validate_evidence_packet(packet: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
        forbidden = FORBIDDEN_EVIDENCE_KEYS.intersection(packet)
        if forbidden:
            raise ValueError(f"private evidence cannot issue command verdict fields: {sorted(forbidden)}")
        if packet.get("mission_id") != task.get("mission_id") or packet.get("task_id") != task.get("task_id"):
            raise ValueError("evidence packet does not belong to the authorized task")
        if packet.get("may_issue_verdict") not in {None, False}:
            raise ValueError("private evidence cannot acquire verdict authority")
        scope = {str(item) for item in task.get("scope", [])}
        for reference in packet.get("evidence_refs", []):
            text = str(reference)
            if "://" in text or not scope:
                continue
            path = text.split(":", 1)[0]
            if path not in scope:
                raise ValueError(f"evidence reference escaped authorized scope: {path}")
        return packet
    ''',
)

write(
    "main_review/workspace_interfaces.py",
    r'''
    """Replaceable Ptah/Hunter Workspace and live-research adapter boundaries."""

    from __future__ import annotations

    from typing import Any, Protocol

    from .operational_contracts import validate_evidence_packet


    class WorkspaceAdapter(Protocol):
        name: str

        def capabilities(self) -> set[str]: ...

        def execute(self, request: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]: ...


    class ResearchAdapter(Protocol):
        name: str

        def capabilities(self) -> set[str]: ...

        def lookup(self, request: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]: ...


    class UnavailableWorkspaceAdapter:
        name = "unavailable-workspace"

        def capabilities(self) -> set[str]:
            return set()

        def execute(self, request: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
            return {**request, "status": "awaiting_adapter", "reason": "No workspace facility is connected."}


    class UnavailableResearchAdapter:
        name = "unavailable-research"

        def capabilities(self) -> set[str]:
            return set()

        def lookup(self, request: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
            return {**request, "status": "awaiting_adapter", "reason": "No governed live-research facility is connected."}


    def dispatch_authorized_requests(
        campaign: dict[str, Any],
        *,
        workspace: WorkspaceAdapter | None = None,
        research: ResearchAdapter | None = None,
    ) -> dict[str, Any]:
        """Dispatch only already-authorized requests; adapters never create authority."""

        workspace = workspace or UnavailableWorkspaceAdapter()
        research = research or UnavailableResearchAdapter()
        tasks = {item["task_id"]: item for item in campaign.get("tasks", [])}
        workspace_results: list[dict[str, Any]] = []
        research_results: list[dict[str, Any]] = []

        for request in campaign.get("workspace_requests", []):
            task = tasks.get(request.get("task_id"))
            if task is None or task.get("status") != "authorized":
                workspace_results.append({**request, "status": "rejected", "reason": "Task is not authorized."})
                continue
            workspace_results.append(workspace.execute(request, task))

        for request in campaign.get("research_requests", []):
            task = tasks.get(request.get("task_id"))
            if task is None or task.get("status") != "authorized":
                research_results.append({**request, "status": "rejected", "reason": "Task is not authorized."})
                continue
            research_results.append(research.lookup(request, task))

        evidence: list[dict[str, Any]] = []
        for result in [*workspace_results, *research_results]:
            packet = result.get("evidence_packet") if isinstance(result, dict) else None
            task = tasks.get(result.get("task_id")) if isinstance(result, dict) else None
            if isinstance(packet, dict) and isinstance(task, dict):
                evidence.append(validate_evidence_packet(packet, task))

        return {
            "workspace_adapter": workspace.name,
            "research_adapter": research.name,
            "workspace_results": workspace_results,
            "research_results": research_results,
            "evidence_packets": evidence,
            "authority_preserved": True,
        }
    ''',
)

write(
    "main_review/cpl_campaign.py",
    r'''
    """Workspace-ready Cpl campaign planning and replay.

    Cpl receives the current ground picture, authorizes specialist work through
    permanent officers, and prepares bounded workspace/research requests.  The
    module does not claim that Ptah facilities are connected; requests remain
    awaiting_adapter until a real adapter returns validated evidence.
    """

    from __future__ import annotations

    import math
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

        if any(marker in text for marker in _SECURITY_MARKERS) or any(item.get("gates_verdict") for item in assurances):
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

        if any(marker in text for marker in _RUNTIME_MARKERS):
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
            if "test_runner" in capabilities:
                facility, action = "test", "run_bounded_regression_or_reproduction"
                artifacts.extend(["test log", "exit status"])
            elif "runtime_tracer" in capabilities or "runtime_reproducer" in capabilities:
                facility, action = "runtime", "reproduce_bounded_execution_world"
                artifacts.extend(["runtime trace", "environment manifest"])
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
        requires_current_lookup = requires_current_lookup or any(marker in text for marker in _CONTRACT_MARKERS)
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
        """Create the next council round from validated evidence without auto-spawning work."""

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
                    "authorization_id": stable_id("authorization", campaign.get("mission", {}).get("mission_id"), task["task_id"], question),
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
        rounds = list(campaign.get("council_rounds", []))
        rounds.append({
            "round_number": len(rounds) + 1,
            "ground_picture": {
                "new_evidence_packets": len(accepted) - len(campaign.get("evidence_packets", [])),
                "new_evidence_refs": sorted(set(evidence_refs)),
                "new_questions": questions,
            },
            "decisions": [
                "Route validated evidence to the responsible officers.",
                "Keep discovered questions pending until officer relevance and Cpl priority are authorized.",
            ],
            "authorized_tasks": [],
            "pending_authorizations": [item["authorization_id"] for item in pending],
            "evidence_saturation": not pending,
            "report_ready_for_sergeant": not pending,
        })
        updated["evidence_packets"] = accepted
        updated["pending_authorizations"] = pending
        updated["council_rounds"] = rounds
        updated["report_ready_for_sergeant"] = not pending
        updated["status"] = "evidence_received" if accepted else campaign.get("status", "prepared")
        return updated
    ''',
)

write(
    "tests/test_workspace_ready_campaign.py",
    r'''
    from __future__ import annotations

    from pathlib import Path

    import pytest

    from main_review.cpl_campaign import advance_campaign, build_cpl_campaign
    from main_review.officer_council import run_officer_council
    from main_review.operational_contracts import (
        evidence_packet,
        private_force_size,
        research_request,
        task_packet,
        validate_evidence_packet,
    )
    from main_review.workspace_interfaces import dispatch_authorized_requests


    def _campaign(tmp_path: Path, *, cpl: dict | None = None, assurances: list[dict] | None = None) -> dict:
        source = tmp_path / "src" / "auth.py"
        source.parent.mkdir(parents=True)
        source.write_text("def refresh(token):\n    return token\n", encoding="utf-8")
        return build_cpl_campaign(
            tmp_path,
            ["src/auth.py", "pyproject.toml"],
            officer_reports=[],
            admitted=[],
            advisory=[],
            rejected=[],
            assurances=assurances or [],
            cpl=cpl or {"status": "disabled", "passes": []},
            offline={"complete": True},
        )


    def test_private_force_scales_human_need_by_ten_with_twenty_minimum() -> None:
        assert private_force_size(1) == 20
        assert private_force_size(2) == 20
        assert private_force_size(5) == 50


    def test_campaign_exists_before_workspace_or_models(tmp_path: Path) -> None:
        campaign = _campaign(tmp_path)
        assert campaign["status"] == "prepared"
        assert campaign["adapter_status"]["workspace"] == "awaiting_adapter"
        assert campaign["model_support"]["status"] == "disabled"
        assert campaign["private_force"]["planned_private_count"] >= 20
        assert campaign["report_ready_for_sergeant"] is True
        assert all(item["status"] == "awaiting_adapter" for item in campaign["workspace_requests"])


    def test_models_are_recorded_as_support_not_officer_identity(tmp_path: Path) -> None:
        campaign = _campaign(tmp_path, cpl={
            "status": "completed",
            "passes": [{"model": "candidate-model", "supported_officer": "Engineer"}],
        })
        assert campaign["model_support"]["passes"] == 1
        assert all(task["responsible_officer"] != "candidate-model" for task in campaign["tasks"])
        assert "do not create the council" in campaign["model_support"]["rule"]


    def test_research_is_bounded_and_waits_for_adapter(tmp_path: Path) -> None:
        campaign = _campaign(tmp_path)
        assert campaign["research_requests"]
        request = campaign["research_requests"][0]
        assert request["privacy"] == "public_metadata_only"
        assert request["status"] == "awaiting_adapter"
        assert request["allowed_sources"] == ["canonical_repository", "official_documentation", "security_advisory"]
        with pytest.raises(ValueError):
            research_request(
                mission_id="m",
                task_id="t",
                question="Look up Authorization: Bearer top-secret",
                allowed_sources=("official_documentation",),
            )


    def test_unavailable_adapters_preserve_requests_without_fabricating_evidence(tmp_path: Path) -> None:
        campaign = _campaign(tmp_path)
        result = dispatch_authorized_requests(campaign)
        assert result["authority_preserved"] is True
        assert result["evidence_packets"] == []
        assert {item["status"] for item in result["workspace_results"]} == {"awaiting_adapter"}


    def test_private_evidence_cannot_issue_verdict_or_escape_scope() -> None:
        task = task_packet(
            mission_id="mission-1",
            officer="Engineer",
            objective="Inspect auth",
            scope=("src/auth.py",),
            questions=("Is it safe?",),
            required_evidence=("path and line",),
            allowed_capabilities=("repository_reader",),
        )
        packet = evidence_packet(
            mission_id="mission-1",
            task_id=task["task_id"],
            worker_id="Private-E1",
            claims=({"claim": "guard exists"},),
            evidence_refs=("src/auth.py:1-2",),
            confidence=0.9,
        )
        assert validate_evidence_packet(packet, task) == packet
        with pytest.raises(ValueError):
            validate_evidence_packet({**packet, "verdict": "PASS"}, task)
        with pytest.raises(ValueError):
            validate_evidence_packet({**packet, "evidence_refs": ["src/other.py:1"]}, task)


    def test_new_private_questions_request_authorization_instead_of_spawning_cells(tmp_path: Path) -> None:
        campaign = _campaign(tmp_path)
        task = next(item for item in campaign["tasks"] if item["execution_mode"] == "private_cell")
        packet = evidence_packet(
            mission_id=campaign["mission"]["mission_id"],
            task_id=task["task_id"],
            worker_id="Private-S1",
            claims=(),
            evidence_refs=(task["scope"][0] + ":1",),
            questions_for_officer=("Does another service invalidate this state?",),
            confidence=0.6,
        )
        advanced = advance_campaign(campaign, [packet])
        assert len(advanced["tasks"]) == len(campaign["tasks"])
        assert advanced["pending_authorizations"][0]["status"] == "pending_officer_and_cpl_authorization"
        assert advanced["pending_authorizations"][0]["recommended_private_count"] == 20
        assert advanced["report_ready_for_sergeant"] is False


    def test_unresolved_required_assurance_prevents_campaign_report_ready(tmp_path: Path) -> None:
        campaign = _campaign(tmp_path, assurances=[{
            "assurance_id": "a1",
            "required_assurance": "runtime proof",
            "status": "unresolved",
            "gates_verdict": True,
            "evidence": "not run",
        }])
        assert campaign["report_ready_for_sergeant"] is False
        assert campaign["council_rounds"][0]["evidence_saturation"] is False


    def test_officer_council_embeds_workspace_ready_campaign(tmp_path: Path) -> None:
        source = tmp_path / "src" / "feature.py"
        source.parent.mkdir(parents=True)
        source.write_text("def feature():\n    return True\n", encoding="utf-8")
        result = run_officer_council(
            tmp_path,
            ["src/feature.py"],
            repository_review={"evidence": {"findings": []}},
            diff={"evidence": {"findings": []}},
            capabilities={"findings": []},
            intelligence={"promoted_findings": []},
            standard={"blockers": []},
            cpl={"status": "disabled", "passes": []},
        )
        assert result["campaign"]["schema_version"] == "sergeant.cpl-campaign.v1"
        assert result["workspace_ready"] is True
        assert result["private_force"]["planned_private_count"] >= 20
    ''',
)

write(
    "docs/46-workspace-ready-cpl-command-fabric.md",
    r'''
    # Workspace-ready Cpl command fabric

    Sergeant now defines the operational contracts required to connect Ptah or
    another Hunter Workspace later without redesigning Cpl, the permanent
    officers, private cells, Hermes, or Sergeant's final authority.

    ## What is implemented now

    - versioned Sergeant mission packets;
    - Cpl campaign and council-round state;
    - permanent-officer task ownership;
    - the 10× private-force rule, with twenty as the minimum formation;
    - hypotheses, falsifiers, dependencies, stop conditions, and escalation rules;
    - bounded workspace and live-research requests;
    - strict evidence packets that cannot issue verdicts or escape scope;
    - pending authorization for newly discovered questions;
    - replayable Hermes transactions and provenance requirements;
    - replaceable workspace and research adapter protocols;
    - model support recorded beneath permanent officers.

    ## What is intentionally not claimed

    No terminal, browser, device, sandbox, or general-web facility is represented
    as connected merely because these contracts exist.  Until a real adapter is
    supplied, authorized requests remain `awaiting_adapter` and produce no
    evidence.  Existing deterministic review remains usable and authoritative.

    ## Connection model

    ```text
    Sergeant mission and proof boundary
        -> Cpl campaign and council round
        -> permanent officer task authorization
        -> 10× private-cell execution plan
        -> Ptah/Hunter Workspace or governed research adapter
        -> validated private evidence packet
        -> responsible officer
        -> Analyst / Challenger / Judge
        -> Cpl complete ground report
        -> Sergeant verdict
    ```

    Models and facilities are capabilities, not ranks.  A model can strengthen an
    Engineer, Medic, Mechanic, Scout, Challenger, or Judge-support assignment, but
    cannot become that officer or issue Sergeant's verdict.  Workspace facilities
    can execute approved tasks, but cannot create authority, expand scope, or
    promote their own output into memory.

    ## Future Ptah adapter expectations

    A Ptah adapter should implement the existing workspace interface and report:

    - capability inventory and facility identity;
    - exact environment and source revision;
    - execution status, logs, tests, traces, screenshots, recordings, or artifacts;
    - evidence and artifact provenance;
    - incomplete or failed task state;
    - privacy and permission enforcement;
    - no final verdict.

    A governed research adapter should accept only bounded questions, apply source
    and domain policy, remove private context, cache results, preserve retrieval
    time and source provenance, disclose conflicts, and return evidence to Scout
    and the responsible officer rather than directly controlling the gate.
    ''',
)

replace_once(
    "main_review/officer_council.py",
    "from .offline_investigation import run_offline_investigations\n",
    "from .cpl_campaign import build_cpl_campaign\nfrom .offline_investigation import run_offline_investigations\n",
)
replace_once(
    "main_review/officer_council.py",
    "    reports = _officer_reports(candidates, admitted, advisory, rejected, assurances, offline, cpl)\n    transactions = _transactions(changed, candidates, admitted, advisory, rejected, assurances)\n",
    "    reports = _officer_reports(candidates, admitted, advisory, rejected, assurances, offline, cpl)\n    campaign = build_cpl_campaign(\n        root,\n        changed,\n        officer_reports=reports,\n        admitted=admitted,\n        advisory=advisory,\n        rejected=rejected,\n        assurances=assurances,\n        cpl=cpl,\n        offline=offline,\n    )\n    transactions = _transactions(changed, candidates, admitted, advisory, rejected, assurances)\n    transactions.extend(campaign.get(\"transactions\", []))\n",
)
replace_once(
    "main_review/officer_council.py",
    "        \"offline_investigation\": offline,\n        \"required_actions\": [\n",
    "        \"offline_investigation\": offline,\n        \"campaign\": campaign,\n        \"workspace_ready\": True,\n        \"private_force\": campaign.get(\"private_force\", {}),\n        \"workspace_adapter_status\": campaign.get(\"adapter_status\", {}).get(\"workspace\"),\n        \"research_adapter_status\": campaign.get(\"adapter_status\", {}).get(\"research\"),\n        \"required_actions\": [\n",
)
replace_once(
    "main_review/pr_reviewer.py",
    "    lines.append(f\"- Unresolved explicit assurances: {len(formation.get('unresolved_assurances', []))}\")\n    lines.append(f\"- Semantic files supplied: {len(packet.get('semantic_files', []))}\")\n",
    "    lines.append(f\"- Unresolved explicit assurances: {len(formation.get('unresolved_assurances', []))}\")\n    campaign = formation.get(\"campaign\", {}) if isinstance(formation, dict) else {}\n    private_force = campaign.get(\"private_force\", {}) if isinstance(campaign, dict) else {}\n    adapter_status = campaign.get(\"adapter_status\", {}) if isinstance(campaign, dict) else {}\n    lines.append(f\"- Cpl campaign status: {campaign.get('status', 'not prepared')}\")\n    lines.append(f\"- Authorized operational tasks: {len(campaign.get('tasks', []))}\")\n    lines.append(f\"- Planned private force: {private_force.get('planned_private_count', 0)}\")\n    lines.append(f\"- Workspace adapter: {adapter_status.get('workspace', 'not prepared')}\")\n    lines.append(f\"- Research adapter: {adapter_status.get('research', 'not prepared')}\")\n    lines.append(f\"- Semantic files supplied: {len(packet.get('semantic_files', []))}\")\n",
)

# The constructor is single-use.  Remove it and its workflow from the product commit.
(ROOT / "scripts" / "apply_workspace_ready_command_fabric.py").unlink(missing_ok=True)
(ROOT / ".github" / "workflows" / "build-workspace-ready-command-fabric.yml").unlink(missing_ok=True)
