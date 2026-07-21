from __future__ import annotations

from pathlib import Path


FROZEN = Path(".github/workflows/model-free-core-transfer-31.yml")
LEARNED = Path(".github/workflows/model-free-core-transfer-31-learned.yml")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_frozen_transfer_propagates_every_selector_v8_truth_flag() -> None:
    workflow = _text(FROZEN)

    for field in (
        "complete_pr_file_pagination_required",
        "capability_addition_exclusion",
        "preexisting_behavioral_contract_evidence_required",
        "feature_enablement_without_defect_rejected",
        "canonical_perl_t_tests_recognized",
    ):
        assert workflow.count(field) >= 2, field


def test_learned_file_sparse_checkouts_disable_cone_mode() -> None:
    workflow = _text(LEARNED)

    assert workflow.count("sparse-checkout-cone-mode: false") == 3
    assert workflow.count("sparse-checkout: |") == 3


def test_transfer_summaries_are_pure_json_not_mixed_execution_logs() -> None:
    for path in (FROZEN, LEARNED):
        workflow = _text(path)
        assert "frozen-execution.log" in workflow
        assert "jq '{set_id, case_count, summaries}'" in workflow
        assert "tee build/model-free-core-transfer-31/frozen-summary.json" not in workflow
        assert "tee build/model-free-core-transfer-31-learned/frozen-summary.json" not in workflow
