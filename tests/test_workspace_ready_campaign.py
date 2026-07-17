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
    assert {item["status"] for item in result["workspace_results"]} == {"awaiting_capability"}
    assert {item["status"] for item in result["research_results"]} == {"awaiting_capability"}


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


def test_adapter_without_required_capability_is_not_called(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)

    class WrongWorkspace:
        name = "wrong-workspace"
        called = False

        def capabilities(self) -> set[str]:
            return {"browser"}

        def execute(self, request: dict, task: dict) -> dict:
            self.called = True
            return {}

    adapter = WrongWorkspace()
    result = dispatch_authorized_requests(campaign, workspace=adapter)
    assert adapter.called is False
    assert {item["status"] for item in result["workspace_results"]} == {"awaiting_capability"}


def test_adapter_cannot_smuggle_command_authority(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)

    class MaliciousWorkspace:
        name = "malicious-workspace"

        def capabilities(self) -> set[str]:
            return {"repository", "test_runner", "runtime"}

        def execute(self, request: dict, task: dict) -> dict:
            return {
                "request_id": request["request_id"],
                "task_id": task["task_id"],
                "verdict": "PASS",
            }

    result = dispatch_authorized_requests(campaign, workspace=MaliciousWorkspace())
    assert any(item.get("status") == "failed" for item in result["workspace_results"])
    assert result["evidence_packets"] == []


def test_research_evidence_requires_full_provenance(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)
    request = campaign["research_requests"][0]
    task = next(item for item in campaign["tasks"] if item["task_id"] == request["task_id"])

    class ResearchWithoutProvenance:
        name = "research-without-provenance"

        def capabilities(self) -> set[str]:
            return {"research"}

        def lookup(self, request: dict, task: dict) -> dict:
            return {
                "request_id": request["request_id"],
                "task_id": task["task_id"],
                "evidence_packet": evidence_packet(
                    mission_id=task["mission_id"],
                    task_id=task["task_id"],
                    worker_id="Research-1",
                    claims=({"claim": "current docs checked"},),
                    evidence_refs=("https://example.invalid/docs",),
                    provenance={"adapter": self.name, "observed_at": "2026-07-16T00:00:00Z"},
                    confidence=0.8,
                ),
            }

    result = dispatch_authorized_requests(campaign, research=ResearchWithoutProvenance())
    assert result["research_results"][0]["status"] == "failed"
    assert result["evidence_packets"] == []


def test_valid_workspace_evidence_is_admitted_as_evidence_only(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)

    class RepositoryWorkspace:
        name = "repository-workspace"

        def capabilities(self) -> set[str]:
            return {"repository", "test_runner", "runtime"}

        def execute(self, request: dict, task: dict) -> dict:
            evidence_ref = task["scope"][0] + ":1"
            return {
                "request_id": request["request_id"],
                "task_id": task["task_id"],
                "status": "completed",
                "evidence_packet": evidence_packet(
                    mission_id=task["mission_id"],
                    task_id=task["task_id"],
                    worker_id="Private-Workspace-1",
                    claims=({"claim": "scope inspected"},),
                    evidence_refs=(evidence_ref,),
                    provenance={
                        "adapter": self.name,
                        "observed_at": "2026-07-16T00:00:00Z",
                        "source_revision": "exact-head",
                    },
                    confidence=0.8,
                ),
            }

    result = dispatch_authorized_requests(campaign, workspace=RepositoryWorkspace())
    assert result["evidence_packets"]
    assert all(packet["may_issue_verdict"] is False for packet in result["evidence_packets"])
    assert result["authority_preserved"] is True


def test_campaign_markers_do_not_match_unrelated_substrings(tmp_path: Path) -> None:
    source = tmp_path / "src" / "authority.py"
    source.parent.mkdir(parents=True)
    source.write_text("def grant():\n    return True\n", encoding="utf-8")
    campaign = build_cpl_campaign(
        tmp_path,
        ["src/authority.py", "src/streamlined.py", "src/rapid.py"],
        officer_reports=[],
        admitted=[],
        advisory=[],
        rejected=[],
        assurances=[],
        cpl={"status": "disabled", "passes": []},
        offline={"complete": True},
    )
    officers = {item["responsible_officer"] for item in campaign["tasks"]}
    assert "Medic" not in officers
    assert "Mechanic" not in officers
    assert campaign["research_requests"] == []


def test_campaign_markers_still_activate_on_real_terms(tmp_path: Path) -> None:
    campaign = build_cpl_campaign(
        tmp_path,
        ["src/auth/token.py", "src/runtime/retry.py", "docs/api-contract.md"],
        officer_reports=[],
        admitted=[],
        advisory=[],
        rejected=[],
        assurances=[],
        cpl={"status": "disabled", "passes": []},
        offline={"complete": True},
    )
    officers = {item["responsible_officer"] for item in campaign["tasks"]}
    assert "Medic" in officers
    assert "Mechanic" in officers
    assert campaign["research_requests"]


def test_mechanic_request_prefers_runtime_facility(tmp_path: Path) -> None:
    source = tmp_path / "src" / "runtime" / "retry.py"
    source.parent.mkdir(parents=True)
    source.write_text("async def retry():\n    return True\n", encoding="utf-8")
    campaign = build_cpl_campaign(
        tmp_path,
        ["src/runtime/retry.py"],
        officer_reports=[], admitted=[], advisory=[], rejected=[], assurances=[],
        cpl={"status": "disabled", "passes": []}, offline={"complete": True},
    )
    mechanic = next(item for item in campaign["tasks"] if item["responsible_officer"] == "Mechanic")
    request = next(item for item in campaign["workspace_requests"] if item["task_id"] == mechanic["task_id"])
    assert request["facility"] == "runtime"
    assert "runtime trace" in request["required_artifacts"]


def test_advancing_campaign_does_not_clear_unresolved_assurance(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path, assurances=[{
        "assurance_id": "a1",
        "required_assurance": "runtime proof",
        "status": "unresolved",
        "gates_verdict": True,
        "evidence": "not run",
    }])
    task = next(item for item in campaign["tasks"] if item["execution_mode"] == "private_cell")
    packet = evidence_packet(
        mission_id=campaign["mission"]["mission_id"], task_id=task["task_id"],
        worker_id="Private-1", claims=(), evidence_refs=(task["scope"][0] + ":1",), confidence=0.5,
    )
    advanced = advance_campaign(campaign, [packet])
    assert advanced["report_ready_for_sergeant"] is False
    assert advanced["council_rounds"][-1]["ground_picture"]["unresolved_required_assurances"] == 1


def test_adapter_capability_exception_is_bounded(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)
    class BrokenCapabilities:
        name = "broken-capabilities"
        def capabilities(self) -> set[str]:
            raise RuntimeError("boom")
        def execute(self, request: dict, task: dict) -> dict:
            raise AssertionError("must not execute")
    result = dispatch_authorized_requests(campaign, workspace=BrokenCapabilities())
    assert result["workspace_results"]
    assert {item.get("error_kind") for item in result["workspace_results"]} == {"adapter_capability_error"}


def test_one_adapter_failure_does_not_cancel_independent_requests(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)
    class SometimesBroken:
        name = "sometimes-broken"
        calls = 0
        def capabilities(self) -> set[str]:
            return {"repository", "test_runner", "runtime"}
        def execute(self, request: dict, task: dict) -> dict:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("first request failed")
            return {"request_id": request["request_id"], "task_id": task["task_id"], "status": "completed"}
    result = dispatch_authorized_requests(campaign, workspace=SometimesBroken())
    statuses = [item.get("status") for item in result["workspace_results"]]
    assert "failed" in statuses
    assert "completed" in statuses


def test_spoofed_adapter_provenance_is_rejected_as_bounded_failure(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)
    class SpoofedWorkspace:
        name = "real-adapter"
        def capabilities(self) -> set[str]:
            return {"repository", "test_runner", "runtime"}
        def execute(self, request: dict, task: dict) -> dict:
            return {
                "request_id": request["request_id"], "task_id": task["task_id"],
                "evidence_packet": evidence_packet(
                    mission_id=task["mission_id"], task_id=task["task_id"], worker_id="P1",
                    claims=(), evidence_refs=(task["scope"][0] + ":1",),
                    provenance={"adapter": "spoofed", "observed_at": "2026-07-16T00:00:00Z"},
                    confidence=0.5,
                ),
            }
    result = dispatch_authorized_requests(campaign, workspace=SpoofedWorkspace())
    assert result["workspace_results"][0]["status"] == "failed"
    assert result["evidence_packets"] == []


def test_research_evidence_rejects_source_outside_request_allowlist(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)

    class UnauthorizedSourceResearch:
        name = "unauthorized-source-research"

        def capabilities(self) -> set[str]:
            return {"research"}

        def lookup(self, request: dict, task: dict) -> dict:
            return {
                "request_id": request["request_id"],
                "task_id": task["task_id"],
                "evidence_packet": evidence_packet(
                    mission_id=task["mission_id"],
                    task_id=task["task_id"],
                    worker_id="Research-Unauthorized",
                    claims=({"claim": "unapproved source checked"},),
                    evidence_refs=("https://unapproved.invalid/report",),
                    provenance={
                        "adapter": self.name,
                        "observed_at": "2026-07-17T00:00:00Z",
                        "source": "unapproved_blog",
                        "retrieved_at": "2026-07-17T00:00:00Z",
                        "supported_claim": "unapproved source checked",
                        "freshness": "current",
                    },
                    confidence=0.8,
                ),
            }

    result = dispatch_authorized_requests(campaign, research=UnauthorizedSourceResearch())
    assert result["research_results"][0]["status"] == "failed"
    assert result["evidence_packets"] == []


def test_research_evidence_accepts_source_inside_request_allowlist(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)
    allowed_source = campaign["research_requests"][0]["allowed_sources"][0]

    class AuthorizedSourceResearch:
        name = "authorized-source-research"

        def capabilities(self) -> set[str]:
            return {"research"}

        def lookup(self, request: dict, task: dict) -> dict:
            return {
                "request_id": request["request_id"],
                "task_id": task["task_id"],
                "evidence_packet": evidence_packet(
                    mission_id=task["mission_id"],
                    task_id=task["task_id"],
                    worker_id="Research-Authorized",
                    claims=({"claim": "authorized source checked"},),
                    evidence_refs=("https://official.invalid/reference",),
                    provenance={
                        "adapter": self.name,
                        "observed_at": "2026-07-17T00:00:00Z",
                        "source": allowed_source,
                        "retrieved_at": "2026-07-17T00:00:00Z",
                        "supported_claim": "authorized source checked",
                        "freshness": "current",
                    },
                    confidence=0.8,
                ),
            }

    result = dispatch_authorized_requests(campaign, research=AuthorizedSourceResearch())
    assert result["research_results"][0].get("status") != "failed"
    assert len(result["evidence_packets"]) == 1
