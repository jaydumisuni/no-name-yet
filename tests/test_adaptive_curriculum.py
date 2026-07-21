from __future__ import annotations

from main_review.adaptive_curriculum import (
    next_difficulty_tier,
    plan_curriculum_round,
    repository_difficulty,
    select_multilingual_candidates,
)


def _candidate(repo: str, language: str, *, files: int, lines: int, packages: int = 1, depth: int = 1, novelty: float = 0.5, cross: bool = False, concurrency: bool = False) -> dict:
    return {
        "repository": repo,
        "language": language,
        "changed_files": files,
        "changed_lines": lines,
        "package_count": packages,
        "dependency_depth": depth,
        "defect_novelty": novelty,
        "cross_component": cross,
        "concurrency_or_lifecycle": concurrency,
        "provenance_complete": True,
    }


def _good() -> dict:
    return {
        "confirmed_defects": 3,
        "confirmed_defects_found": 3,
        "false_positives": 0,
        "provenance_complete": True,
        "evidence_integrity": True,
    }


def test_difficulty_and_semantic_risk_raise_tier() -> None:
    assert repository_difficulty(_candidate("o/a", "python", files=3, lines=100)) == 0
    assert repository_difficulty(_candidate("o/b", "java", files=10, lines=2_000)) == 1
    assert repository_difficulty(_candidate("o/c", "rust", files=70, lines=15_000, packages=7, depth=8, concurrency=True)) == 4


def test_three_clean_rounds_promote_only_one_tier() -> None:
    assert next_difficulty_tier(0, [_good(), _good(), _good()]) == 1
    assert next_difficulty_tier(3, [_good(), _good(), _good()]) == 4


def test_incomplete_integrity_holds_tier() -> None:
    rows = [_good(), _good(), {**_good(), "evidence_integrity": False}]
    assert next_difficulty_tier(2, rows) == 2


def test_promoted_plan_fails_closed_without_harder_candidate() -> None:
    plan = plan_curriculum_round(
        candidates=[_candidate("o/tiny", "python", files=3, lines=100)],
        current_tier=0,
        recent_results=[_good(), _good(), _good()],
        language_history=["java"],
        count=1,
    )
    assert plan["target_tier"] == 1
    assert plan["cases"] == []
    assert plan["candidate_shortfall"] is True


def test_rust_accelerates_but_cannot_dominate() -> None:
    candidates = [
        _candidate("o/rust", "rust", files=10, lines=1_500, concurrency=True),
        _candidate("o/python", "python", files=10, lines=1_500),
        _candidate("o/java", "java", files=10, lines=1_500),
    ]
    selected = select_multilingual_candidates(
        candidates,
        target_tier=1,
        language_history=["rust", "python", "rust", "ocaml", "swift"],
        count=2,
    )
    assert [row["language"] for row in selected] == ["python", "java"]


def test_force_scales_with_ten_times_law() -> None:
    focused = select_multilingual_candidates(
        [_candidate("o/f", "python", files=3, lines=100)],
        target_tier=0,
        language_history=["java"],
        count=1,
    )[0]
    complex_case = select_multilingual_candidates(
        [_candidate("o/c", "rust", files=75, lines=20_000, packages=8, depth=9, novelty=0.9, cross=True, concurrency=True)],
        target_tier=4,
        language_history=["java"],
        count=1,
    )[0]
    assert focused["human_equivalent_workers"] == 2
    assert focused["private_count"] == 20
    assert complex_case["human_equivalent_workers"] == 12
    assert complex_case["private_count"] == 120


def test_planner_has_no_promotion_or_merge_authority() -> None:
    plan = plan_curriculum_round(
        candidates=[_candidate("o/r", "julia", files=3, lines=100)],
        current_tier=0,
        recent_results=[],
        language_history=[],
        count=1,
    )
    assert plan["authority"] == {"may_promote_lessons": False, "may_merge": False, "final_verdict": "Sergeant"}
