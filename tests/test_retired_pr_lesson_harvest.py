from __future__ import annotations

from collections import Counter
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / ".github" / "self-learning" / "lessons"
CANDIDATES = ROOT / ".github" / "self-learning" / "retrospective-candidates-20260724.json"
HARVEST = ROOT / "docs" / "53-retired-pr-lesson-harvest.md"
WEEK_HISTORY = ROOT / ".github" / "self-learning" / "week-1-history.json"

RETROSPECTIVE_LESSONS = {
    "cpl-adjudication-noise-20260724": "cpl-adjudication-noise-20260724.json",
    "review-evidence-integrity-20260724": "review-evidence-integrity-20260724.json",
    "preserve-before-delete-20260724": "preserve-before-delete-20260724.json",
}
EXPECTED_CANDIDATE_IDS = {
    "pr107-editor-invalid-fallback",
    "pr107-keystroke-expensive-render",
    "pr108-frozen-sha-enforcement",
    "pr108-incomplete-council-success-gate",
    "pr108-null-guard-before-side-effects",
    "pr108-atomic-check-update",
    "pr133-mobile-critical-control-proof",
}
EXPECTED_SOURCE_COUNTS = {107: 2, 108: 4, 133: 1}
EXPECTED_REJECTED_DISPOSITIONS = {
    ((141,), "duplicate"),
    ((105,), "superseded"),
    ((65, 47), "superseded"),
    ((132,), "design_reference"),
    ((124, 125, 126, 127, 128), "accepted_via_pr_130"),
    ((118, 117, 116, 115, 114, 113), "evidence_only"),
    ((104, 97), "observer_only"),
}


def _read_json(path: Path) -> dict:
    """Read one UTF-8 JSON record from the repository."""
    return json.loads(path.read_text(encoding="utf-8"))


def test_retrospective_lessons_are_accepted_proof_bound_and_not_automatic() -> None:
    for lesson_id, filename in RETROSPECTIVE_LESSONS.items():
        lesson = _read_json(LESSONS / filename)
        assert lesson["schema_version"] == "sergeant.accepted-lesson.v1"
        assert lesson["lesson_id"] == lesson_id
        assert lesson["status"] == "accepted"
        assert lesson["authority"]["promotion_mode"] == "owner_controlled_retrospective"
        assert lesson["authority"]["may_auto_promote"] is False
        assert lesson["authority"]["may_auto_merge"] is False
        assert lesson["authority"]["final_verdict"] == "Sergeant"
        assert lesson["promotion_gate"]["existing_model_free_implementation_verified"] is True
        assert lesson["promotion_gate"]["focused_regressions_present"] is True
        assert lesson["promotion_gate"]["clean_controls_present"] is True
        assert lesson["promotion_gate"]["historical_exact_head_proof_present"] is True
        assert lesson["promotion_gate"]["retrospective_harvest_exact_head_pending"] is False
        assert lesson["proof"]["retrospective_admission_proof_head"] == (
            "8fae3921495ea8d0501f645a958878eb9ac81903"
        )
        assert "CodeRabbit" in lesson["proof"]["external_review_disposition"]

        for relative in lesson["implementation"]["files"]:
            assert (ROOT / relative).is_file(), relative
        for relative in lesson["implementation"]["tests"]:
            assert (ROOT / relative).is_file(), relative


def test_unproven_findings_remain_candidates_or_benchmarks() -> None:
    record = _read_json(CANDIDATES)
    candidates = record["candidates"]
    assert record["automatic_promotions"] == 0
    assert record["automatic_merges"] == 0
    assert len(candidates) == 7
    assert {item["candidate_id"] for item in candidates} == EXPECTED_CANDIDATE_IDS
    assert Counter(item["source_pr"] for item in candidates) == EXPECTED_SOURCE_COUNTS
    assert {item["status"] for item in candidates} == {"needs_lineage", "benchmark_only"}
    assert not any(item.get("status") == "accepted" for item in candidates)
    assert all(item.get("missing_gates") for item in candidates)

    by_id = {item["candidate_id"]: item for item in candidates}
    invalid_fallback = by_id["pr107-editor-invalid-fallback"]
    expensive_render = by_id["pr107-keystroke-expensive-render"]
    assert invalid_fallback["source_pr"] == 107
    assert invalid_fallback["source_prs"] == [106, 107]
    assert invalid_fallback["original_battle_pr"] == 106
    assert invalid_fallback["reviewed_replacement_pr"] == 107
    assert expensive_render["source_prs"] == [106, 107]
    assert by_id["pr133-mobile-critical-control-proof"]["status"] == "benchmark_only"

    actual_dispositions = {
        (tuple(item["prs"]), item["disposition"])
        for item in record["rejected_or_duplicate_sources"]
    }
    assert actual_dispositions == EXPECTED_REJECTED_DISPOSITIONS
    assert all(item.get("reason") for item in record["rejected_or_duplicate_sources"])


def test_harvest_accounts_for_every_branch_retirement_pr_group() -> None:
    text = HARVEST.read_text(encoding="utf-8")
    for token in (
        "#141",
        "#105",
        "#65, #47",
        "#132",
        "#96",
        "#133",
        "#124–#128",
        "#118–#113",
        "#106/#107",
        "#108",
        "#104, #97",
    ):
        assert token in text
    assert "PR #106 was the original invalidated battle" in text
    assert "PR #107 reviewed identical target bytes" in text
    assert "Closing a pull request preserves its Git history, but preservation alone is not learning." in text
    assert "Automatic promotion and automatic merge remain forbidden." in text


def test_week_one_history_is_not_rewritten_by_retrospective_harvest() -> None:
    history = _read_json(WEEK_HISTORY)
    assert history["accepted_lessons"] == 1
    assert history["accepted_lesson_ids"] == ["lumi-token-origin-20260723"]
    assert history["automatic_promotions"] == 0
    assert history["automatic_merges"] == 0
