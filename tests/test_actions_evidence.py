from __future__ import annotations

import json
from pathlib import Path

from main_review.actions_evidence import cleanup_eligible, retained_bytes, validate_preservation_ledger


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "evidence" / "actions" / "2026-07-22-preservation-ledger.json"


def test_preservation_ledger_is_complete_and_deletion_is_disabled() -> None:
    payload = json.loads(LEDGER.read_text(encoding="utf-8"))

    assert validate_preservation_ledger(payload) == []
    assert payload["artifact_count"] == 29
    assert payload["total_bytes"] == 13_772_291
    assert payload["deletion_authorized"] is False
    assert payload["workflow_run_deletion_authorized"] is False
    assert retained_bytes(payload["records"]) == payload["total_bytes"]


def test_unique_failures_and_learning_evidence_are_retained() -> None:
    payload = json.loads(LEDGER.read_text(encoding="utf-8"))
    by_name = {record["name"]: record for record in payload["records"]}

    assert by_name["controlled-self-learning-week-1-run-9.zip"]["sha256"] == (
        "76300275f3e25aefe542d65c45bc767c767d075e28d98295bdcbc2dc176d12ea"
    )
    assert by_name["transfer33-parent-rerun-failure.zip"]["deletion_authorized"] is False
    assert by_name["model-free-core-transfer-30-attempt2.zip"]["deletion_authorized"] is False
    assert by_name["final-static-transfer-holdout.zip"]["deletion_authorized"] is False


def test_cleanup_fails_closed_without_every_explicit_gate() -> None:
    record = {
        "name": "candidate.zip",
        "size_bytes": 1,
        "sha256": "a" * 64,
        "size_verified": True,
        "deletion_authorized": True,
        "github": {"artifact_id": 123},
    }

    assert cleanup_eligible(
        record,
        owner_authorized=False,
        recovery_replay_verified=True,
        content_equivalent=True,
    ) is False
    assert cleanup_eligible(
        record,
        owner_authorized=True,
        recovery_replay_verified=False,
        content_equivalent=True,
    ) is False
    assert cleanup_eligible(
        record,
        owner_authorized=True,
        recovery_replay_verified=True,
        content_equivalent=False,
    ) is False
    assert cleanup_eligible(
        record,
        owner_authorized=True,
        recovery_replay_verified=True,
        content_equivalent=True,
    ) is True


def test_current_ledger_cannot_be_used_as_a_cleanup_manifest() -> None:
    payload = json.loads(LEDGER.read_text(encoding="utf-8"))

    assert not any(
        cleanup_eligible(
            record,
            owner_authorized=True,
            recovery_replay_verified=True,
            content_equivalent=True,
        )
        for record in payload["records"]
    )
