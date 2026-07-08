from __future__ import annotations

import json
from pathlib import Path

import pytest

from main_review.app_bridge import handle_app_review_request
from main_review.cli import main
from main_review.v2_mission import (
    MISSION_TYPES,
    V2_CONTRACT_VERSION,
    default_weapon_manifests,
    normalize_mission_request,
    run_v2_mission,
)


def _make_repo(root: Path) -> None:
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / "main_review").mkdir()
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("def handler(request):\n    return request.args.get('name')\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "19-thetechguy-engineering-standard.md").write_text("# Standard\n", encoding="utf-8")


def test_v2_normalizes_complete_mission_contract() -> None:
    payload = normalize_mission_request({
        "root": ".",
        "mode": "pull_request",
        "changed_files": "src/app.py\ntests/test_app.py",
        "branch": "feature/v2",
        "commit": "abc123",
        "pull_request": {"number": 12},
        "policy_profile": "thetechguy",
        "enterprise_profile": {"required_tests": True},
        "time_budget": {"seconds": 30},
        "execution_permissions": {"allow_network": True},
        "output_preferences": {"target": "ide"},
    })

    assert payload["schema_version"] == V2_CONTRACT_VERSION
    assert payload["mission_type"] == "pull_request_review"
    assert payload["changed_files"] == ["src/app.py", "tests/test_app.py"]
    assert payload["execution_permissions"]["read_only"] is True
    assert payload["execution_permissions"]["allow_network"] is True
    assert payload["execution_permissions"]["allow_write"] is False
    assert payload["output_preferences"]["target"] == "ide"


def test_v2_rejects_unknown_mission_type() -> None:
    with pytest.raises(ValueError):
        normalize_mission_request({"mission_type": "random_review"})


def test_v2_weapon_manifests_declare_required_safety_fields() -> None:
    manifests = default_weapon_manifests()

    assert manifests
    assert {manifest["weapon_id"] for manifest in manifests} >= {"repository_scanner", "capability_engine", "evidence_consensus"}
    for manifest in manifests:
        assert manifest["category"] in {"knowledge", "analysis", "reasoning", "evidence", "delivery"}
        assert manifest["maturity_level"] in {"experimental", "testing", "field_tested", "battle_proven", "approved", "standard_issue", "legacy", "retired"}
        assert manifest["executes_code"] is False
        assert manifest["modifies_files"] is False
        assert "test_requirements" in manifest
        assert isinstance(manifest["officer_compatibility"], list)


def test_v2_mission_builds_briefing_loadout_confidence_and_audit(tmp_path: Path) -> None:
    _make_repo(tmp_path)

    payload = run_v2_mission({
        "root": str(tmp_path),
        "mode": "pull_request",
        "changed_files": ["src/app.py", "tests/test_app.py"],
        "mission_type": "pull_request_review",
    })

    assert payload["ok"] is True
    assert payload["schema_version"] == V2_CONTRACT_VERSION
    assert payload["commander"] == "Sergeant"
    assert payload["doctrine"]["highest_law"].startswith("Sergeant commands")
    assert payload["mission_briefing"]["detected_languages"]["Python"] >= 2
    assert "GitHub Actions" in payload["mission_briefing"]["ci_cd_systems"]
    assert "quartermaster" in payload["deployment"]["deployed_officers"]
    assert "engineer" in payload["deployment"]["deployed_officers"]
    assert payload["deployment"]["skipped_officers"]
    assert payload["armoury"]["strategy"] == "minimal_effective_loadout"
    assert payload["confidence"]["mission_confidence"] > 0
    assert payload["safety"]["read_only_default"] is True
    assert payload["safety"]["executes_untrusted_code"] is False
    audit_events = [entry["event"] for entry in payload["audit"]]
    assert "mission_received" in audit_events
    assert "briefing_created" in audit_events


def test_v2_security_mission_deploys_medic_and_blocks_network_weapon_by_default(tmp_path: Path) -> None:
    _make_repo(tmp_path)

    payload = run_v2_mission({
        "root": str(tmp_path),
        "mission_type": "security_review",
        "changed_files": ["src/app.py"],
    })

    assert "medic" in payload["deployment"]["deployed_officers"]
    assert any(item["weapon_id"] == "github_live_reader" for item in payload["armoury"]["unavailable_weapons"])


def test_v2_app_bridge_preserves_v1_response_and_adds_optional_v2_packet(tmp_path: Path) -> None:
    _make_repo(tmp_path)

    payload = handle_app_review_request({
        "root": str(tmp_path),
        "mode": "pull_request",
        "mission_type": "pull_request_review",
        "changed_files": ["src/app.py", "tests/test_app.py"],
    })

    assert payload["ok"] is True
    assert payload["schema_version"] == "sergeant.review.v1"
    assert payload["request"]["mode"] == "pull_request"
    assert "markdown" in payload
    assert payload["v2"]["schema_version"] == V2_CONTRACT_VERSION
    assert payload["v2"]["interfaces"]["optional_v2_fields"] is True


def test_v2_cli_runs(tmp_path: Path) -> None:
    _make_repo(tmp_path)

    assert main(["v2-mission", str(tmp_path), "--mission-type", "pull_request_review", "--mode", "pull_request", "--files", "src/app.py,tests/test_app.py"]) == 0


def test_v2_cli_rejects_unknown_mission_type(tmp_path: Path) -> None:
    _make_repo(tmp_path)

    with pytest.raises(SystemExit) as exc:
        main(["v2-mission", str(tmp_path), "--mission-type", "random_review"])

    assert exc.value.code == 2


def test_v2_cli_allow_write_clears_read_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _make_repo(tmp_path)

    assert main(["v2-mission", str(tmp_path), "--allow-write"]) == 0

    payload = json.loads(capsys.readouterr().out)
    permissions = payload["mission"]["execution_permissions"]
    assert permissions["allow_write"] is True
    assert permissions["read_only"] is False


def test_v2_declares_all_core_mission_types() -> None:
    assert MISSION_TYPES >= {
        "repository_review",
        "pull_request_review",
        "changed_files_review",
        "security_review",
        "architecture_review",
        "performance_review",
        "regression_review",
        "documentation_review",
        "benchmark_review",
        "learning_review",
        "emergency_review",
        "external_review_comparison",
        "release_gate_review",
    }
