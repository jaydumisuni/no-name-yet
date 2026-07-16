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


_FACILITY_CAPABILITY = {
    "repository": "repository",
    "test": "test_runner",
    "runtime": "runtime",
    "browser": "browser",
    "device": "device",
    "artifact": "artifact_store",
}
_FORBIDDEN_RESULT_KEYS = {
    "mission",
    "tasks",
    "authorized_tasks",
    "pending_authorizations",
    "verdict",
    "final_verdict",
    "sergeant_verdict",
}


def _safe_capabilities(adapter: object) -> set[str]:
    capabilities = getattr(adapter, "capabilities", None)
    if not callable(capabilities):
        return set()
    return {str(item) for item in capabilities() if str(item)}


def _validate_result(result: object, request: dict[str, Any], task: dict[str, Any], adapter_name: str) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError(f"{adapter_name} returned a non-object result")
    forbidden = _FORBIDDEN_RESULT_KEYS.intersection(result)
    if forbidden:
        raise ValueError(f"{adapter_name} attempted to return command-authority fields: {sorted(forbidden)}")
    if result.get("request_id") not in {None, request.get("request_id")}:
        raise ValueError(f"{adapter_name} returned evidence for another request")
    if result.get("task_id") not in {None, task.get("task_id")}:
        raise ValueError(f"{adapter_name} returned evidence for another task")
    normalized = {
        **result,
        "request_id": request.get("request_id"),
        "mission_id": task.get("mission_id"),
        "task_id": task.get("task_id"),
        "adapter": adapter_name,
    }
    return normalized


def _validate_adapter_evidence(result: dict[str, Any], task: dict[str, Any], *, research: bool) -> dict[str, Any] | None:
    packet = result.get("evidence_packet")
    if not isinstance(packet, dict):
        return None
    provenance = packet.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("adapter evidence requires provenance")
    required = {"adapter", "observed_at"}
    if research:
        required.update({"source", "retrieved_at", "supported_claim", "freshness"})
    missing = sorted(key for key in required if not provenance.get(key))
    if missing:
        raise ValueError(f"adapter evidence is missing provenance fields: {missing}")
    return validate_evidence_packet(packet, task)


def dispatch_authorized_requests(
    campaign: dict[str, Any],
    *,
    workspace: WorkspaceAdapter | None = None,
    research: ResearchAdapter | None = None,
) -> dict[str, Any]:
    """Dispatch only already-authorized requests; adapters never create authority."""

    workspace = workspace or UnavailableWorkspaceAdapter()
    research = research or UnavailableResearchAdapter()
    workspace_capabilities = _safe_capabilities(workspace)
    research_capabilities = _safe_capabilities(research)
    tasks = {item["task_id"]: item for item in campaign.get("tasks", [])}
    workspace_results: list[dict[str, Any]] = []
    research_results: list[dict[str, Any]] = []

    for request in campaign.get("workspace_requests", []):
        task = tasks.get(request.get("task_id"))
        if task is None or task.get("status") != "authorized":
            workspace_results.append({**request, "status": "rejected", "reason": "Task is not authorized."})
            continue
        if not set(request.get("scope", [])).issubset(set(task.get("scope", []))):
            workspace_results.append({**request, "status": "rejected", "reason": "Request escaped task scope."})
            continue
        required = _FACILITY_CAPABILITY.get(str(request.get("facility") or ""), str(request.get("facility") or ""))
        if required and required not in workspace_capabilities:
            workspace_results.append({
                **request,
                "status": "awaiting_capability",
                "reason": f"Workspace adapter does not provide required capability: {required}",
            })
            continue
        result = workspace.execute(request, task)
        workspace_results.append(_validate_result(result, request, task, workspace.name))

    for request in campaign.get("research_requests", []):
        task = tasks.get(request.get("task_id"))
        if task is None or task.get("status") != "authorized":
            research_results.append({**request, "status": "rejected", "reason": "Task is not authorized."})
            continue
        if "research" not in research_capabilities:
            research_results.append({
                **request,
                "status": "awaiting_capability",
                "reason": "Research adapter does not provide governed research capability.",
            })
            continue
        result = research.lookup(request, task)
        research_results.append(_validate_result(result, request, task, research.name))

    evidence: list[dict[str, Any]] = []
    for result in workspace_results:
        task = tasks.get(result.get("task_id"))
        if isinstance(task, dict):
            packet = _validate_adapter_evidence(result, task, research=False)
            if packet is not None:
                evidence.append(packet)
    for result in research_results:
        task = tasks.get(result.get("task_id"))
        if isinstance(task, dict):
            packet = _validate_adapter_evidence(result, task, research=True)
            if packet is not None:
                evidence.append(packet)

    return {
        "workspace_adapter": workspace.name,
        "workspace_capabilities": sorted(workspace_capabilities),
        "research_adapter": research.name,
        "research_capabilities": sorted(research_capabilities),
        "workspace_results": workspace_results,
        "research_results": research_results,
        "evidence_packets": evidence,
        "authority_preserved": True,
    }
