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
