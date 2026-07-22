from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from main_review.actions_evidence import (
    CLEANUP_MANIFEST_SCHEMA_VERSION,
    cleanup_eligible,
    retained_bytes,
    validate_preservation_ledger,
    validate_recovery_replay,
)


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "evidence" / "actions" / "2026-07-22-preservation-ledger.json"
REPLAY = ROOT / "evidence" / "actions" / "2026-07-22-recovery-replay.json"
CLI = ROOT / "scripts" / "validate_actions_evidence.py"


def _ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(ROOT) if not existing else f"{ROOT}{os.pathsep}{existing}"
    return env


def test_preservation_ledger_is_complete_and_deletion_is_disabled() -> None:
    payload = _ledger()

    assert validate_preservation_ledger(payload) == []
    assert payload["artifact_count"] == 29
    assert payload["total_bytes"] == 13_772_291
    assert payload["deletion_authorized"] is False
    assert payload["workflow_run_deletion_authorized"] is False
    assert retained_bytes(payload["records"]) == payload["total_bytes"]


def test_all_durable_copies_were_downloaded_and_digest_verified() -> None:
    ledger = _ledger()
    replay = json.loads(REPLAY.read_text(encoding="utf-8"))

    assert validate_recovery_replay(ledger, replay) == []
    assert replay["artifact_count"] == replay["verified_count"] == 29
    assert replay["failed_count"] == 0
    assert replay["total_bytes"] == 13_772_291
    assert replay["cleanup_authorized"] is False
    assert replay["workflow_run_deletion_authorized"] is False
    assert all(record["recovery_replay_verified"] is True for record in replay["records"])


def test_recovery_replay_fails_on_digest_or_inventory_drift() -> None:
    ledger = _ledger()
    replay = json.loads(REPLAY.read_text(encoding="utf-8"))

    replay["records"][0]["sha256"] = "0" * 64
    replay["records"].pop()
    errors = validate_recovery_replay(ledger, replay)

    assert any(error.startswith("replay missing artifacts:") for error in errors)
    assert any(error.startswith("recovery digest mismatch:") for error in errors)
    assert "replay artifact_count does not match records" in errors


def test_unique_failures_and_learning_evidence_are_retained() -> None:
    payload = _ledger()
    by_name = {record["name"]: record for record in payload["records"]}

    assert by_name["controlled-self-learning-week-1-run-9.zip"]["sha256"] == (
        "76300275f3e25aefe542d65c45bc767c767d075e28d98295bdcbc2dc176d12ea"
    )
    assert by_name["transfer33-parent-rerun-failure.zip"]["deletion_authorized"] is False
    assert by_name["model-free-core-transfer-30-attempt2.zip"]["deletion_authorized"] is False
    assert by_name["final-static-transfer-holdout.zip"]["deletion_authorized"] is False


def test_ledger_rejects_non_object_root_and_missing_top_level_provenance() -> None:
    assert validate_preservation_ledger([]) == ["Actions evidence ledger root must be an object"]

    cases = {
        "repository": "ledger repository is required",
        "durable_root": "ledger durable_root is required",
        "generated_at": "ledger generated_at must be a valid timestamp",
    }
    for key, expected in cases.items():
        payload = _ledger()
        payload[key] = ""
        assert expected in validate_preservation_ledger(payload)

    payload = _ledger()
    payload["generated_at"] = "not-a-timestamp"
    assert "ledger generated_at must be a valid timestamp" in validate_preservation_ledger(payload)


def test_boolean_size_is_rejected_and_not_counted() -> None:
    payload = _ledger()
    payload["records"][0]["size_bytes"] = True
    errors = validate_preservation_ledger(payload)

    assert "records[0].size_bytes must be a non-negative integer" in errors
    assert retained_bytes([{"size_bytes": True}, {"size_bytes": 4}]) == 4


def test_cleanup_requires_matching_exact_artifact_manifest_and_every_gate() -> None:
    record = {
        "name": "candidate.zip",
        "size_bytes": 1,
        "sha256": "a" * 64,
        "size_verified": True,
        "deletion_authorized": True,
        "github": {"artifact_id": 123},
    }
    matching = {
        "schema_version": CLEANUP_MANIFEST_SCHEMA_VERSION,
        "owner_authorized": True,
        "artifact_id": 123,
    }
    mismatch = {**matching, "artifact_id": 456}

    assert cleanup_eligible(
        record,
        cleanup_manifest=None,
        recovery_replay_verified=True,
        content_equivalent=True,
    ) is False
    assert cleanup_eligible(
        record,
        cleanup_manifest=mismatch,
        recovery_replay_verified=True,
        content_equivalent=True,
    ) is False
    assert cleanup_eligible(
        record,
        cleanup_manifest=matching,
        recovery_replay_verified=False,
        content_equivalent=True,
    ) is False
    assert cleanup_eligible(
        record,
        cleanup_manifest=matching,
        recovery_replay_verified=True,
        content_equivalent=False,
    ) is False
    assert cleanup_eligible(
        record,
        cleanup_manifest=matching,
        recovery_replay_verified=True,
        content_equivalent=True,
    ) is True


def test_current_ledger_cannot_be_used_as_a_cleanup_manifest() -> None:
    payload = _ledger()

    assert not any(
        cleanup_eligible(
            record,
            cleanup_manifest={
                "schema_version": CLEANUP_MANIFEST_SCHEMA_VERSION,
                "owner_authorized": True,
                "artifact_id": record.get("github", {}).get("artifact_id"),
            },
            recovery_replay_verified=True,
            content_equivalent=True,
        )
        for record in payload["records"]
    )


def test_cli_reports_invalid_json_and_non_object_roots(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(CLI), str(invalid)],
        cwd=ROOT,
        env=_cli_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "invalid ledger JSON" in result.stdout

    non_object = tmp_path / "array.json"
    non_object.write_text("[]", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(CLI), str(non_object)],
        cwd=ROOT,
        env=_cli_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Actions evidence ledger root must be an object" in result.stdout
