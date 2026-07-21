from __future__ import annotations

import pytest

from main_review.training_manifest_provenance import ProvenanceError
from scripts import run_static_training_set as runner


def test_untouched_transfer_cannot_opt_out_of_provenance() -> None:
    manifest = {
        "rules": {
            "classification": "untouched_transfer_validation",
            "provenance_contract": "sergeant.training-provenance.v1",
            "reviewer_code_frozen_before_target_selection": "a" * 40,
        },
        "cases": [{"case_id": "fresh-a"}],
    }

    with pytest.raises(ProvenanceError, match="cannot opt out"):
        runner._validate_provenance_policy(manifest, manifest["rules"])


def test_untouched_transfer_always_calls_manifest_validator(monkeypatch) -> None:
    manifest = {
        "set_id": "fresh-set",
        "rules": {
            "classification": "untouched_transfer_validation",
            "provenance_required": True,
        },
        "cases": [{"case_id": "fresh-a"}],
    }
    expected = {"status": "verified", "case_count": 1}
    calls: list[dict] = []

    def fake_validate(packet: dict):
        calls.append(packet)
        return expected

    monkeypatch.setattr(runner, "validate_training_manifest", fake_validate)

    assert runner._validate_provenance_policy(manifest, manifest["rules"]) == expected
    assert calls == [manifest]


def test_learned_closure_without_provenance_flag_remains_separate(monkeypatch) -> None:
    manifest = {
        "rules": {
            "classification": "learned_closure",
            "historical_fresh_score_immutable": True,
        },
        "cases": [{"case_id": "learned-a"}],
    }

    def unexpected_validate(packet: dict):
        raise AssertionError("learned closure must not rewrite the frozen fresh proof")

    monkeypatch.setattr(runner, "validate_training_manifest", unexpected_validate)

    assert runner._validate_provenance_policy(manifest, manifest["rules"]) is None
