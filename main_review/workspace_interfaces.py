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
