from __future__ import annotations

from main_review.adaptive_curriculum import (
    next_difficulty_tier,
    plan_curriculum_round,
    repository_difficulty,
    select_multilingual_candidates,
)


def _candidate(
    repository: str,
    language: str,
    *,
    changed_files: int,
    changed_lines: int,
    package_count: int = 1,
    dependency_depth: int = 1,
    novelty: float = 0.5,
    cross_component: bool = False,
    concurrency: bool = False,
) -> dict:
    return {
        "candidate_id": repository.replace("/", "-"),
        "repository": repository,
        "language": language,
        "changed_files": changed_files,
        "changed_lines": changed_lines,
        "package_count": package_count,
        "dependency_depth": dependency_depth,
        "defect_novelty": novelty,
        "cross_component": cross_component,
        "concurrency_or_lifecycle": concurrency,
        "provenance_complete": True,
    }


def _clean_result(*, confirmed: int = 3, found: int = 3) -> dict:
    return {
        "confirmed_defects": confirmed,
        "confirmed_defects_found": found,
        "false_positives": 0,
        "provenance_complete": True,
        "evidence_integrity": True,
    }


def test_repository_difficulty_rises_with_scope_and_semantic_risk() -> None:
    focused = _candidate("org/focused", "python", changed_files=3, changed_lines=120)
    component = _candidate("org/component", "java", changed_files=9, changed_lines=1_600)
    system = _candidate(
        "org/system",
        "rust",
        changed_files=72,
        changed_lines=14_000,
        package_count=7,
        dependency_depth=8,
        novelty=0.9,
        concurrency=True,
    )

    assert repository_difficulty(focused) == 0
    assert repository_difficulty(component) == 1
    assert repository_difficulty(system) == 4


def test_three_strong_rounds_promote_exactly_one_tier() -> None:
    results = [_clean_result(), _clean_result(), _clean_result()]
    assert next_difficulty_tier(0, results) == 1
    assert next_difficulty_tier(3, results) == 4
    assert next_difficulty_tier(4, results) == 4


def test_missing_integrity_or_excess_noise_holds_difficulty() -> None:
    incomplete = [_clean_result(), _clean_result(), {**_clean_result(), "provenance_complete": False}]
    noisy = [
        _clean_result(),
        _clean_result(),
        {**_clean_result(confirmed=2, found=2), "false_positives": 2},
    ]

    assert next_difficulty_tier(2, incomplete) == 2
    assert next_difficulty_tier(2, noisy) == 2


def test_success_moves_selection_to_a_larger_repository() -> None:
    candidates = [
        _candidate("org/tiny", "python", changed_files=3, changed_lines=100),
        _candidate("org/bigger", "java", changed_files=10, changed_lines=2_000),
        _candidate("org/largest", "rust", changed_files=45, changed_lines=10_000, package_count=6),
    ]
    plan = plan_curriculum_round(
        candidates=candidates,
        current_tier=0,
        recent_results=[_clean_result(), _clean_result(), _clean_result()],
        language_history=["ocaml"],
        count=1,
    )

    assert plan["target_tier"] == 1
    assert plan["cases"][0]["repository"] == "org/bigger"
    assert plan["cases"][0]["difficulty_tier"] == 1


def test_rust_accelerates_without_dominating_language_rotation() -> None:
    candidates = [
        _candidate("org/rust-next", "rust", changed_files=10, changed_lines=1_800, concurrency=True),
        _candidate("org/python-next", "python", changed_files=10, changed_lines=1_800),
        _candidate("org/java-next", "java", changed_files=10, changed_lines=1_800),
    ]
    selected = select_multilingual_candidates(
        candidates,
        target_tier=1,
        language_history=["rust", "python", "rust", "ocaml", "swift"],
        count=2,
    )

    assert [item["language"] for item in selected] == ["python", "java"]
    assert all(item["language"] != "rust" for item in selected)


def test_same_language_and_family_do_not_repeat_until_rotation_allows_it() -> None:
    candidates = [
        _candidate("org/rust", "rust", changed_files=10, changed_lines=1_800),
        _candidate("org/cpp", "cpp", changed_files=10, changed_lines=1_800),
        _candidate("org/zig", "zig", changed_files=10, changed_lines=1_800),
        _candidate("org/elixir", "elixir", changed_files=10, changed_lines=1_800),
    ]
    selected = select_multilingual_candidates(
        candidates,
        target_tier=1,
        language_history=["c", "go"],
        count=2,
    )

    assert selected[0]["language"] == "elixir"
    assert selected[0]["language_family"] == "functional-runtime"


def test_private_force_scales_with_repository_difficulty_using_ten_times_law() -> None:
    focused = _candidate("org/focused", "python", changed_files=3, changed_lines=100)
    complex_case = _candidate(
        "org/complex",
        "rust",
        changed_files=72,
        changed_lines=14_000,
        package_count=7,
        dependency_depth=8,
        novelty=0.9,
        cross_component=True,
        concurrency=True,
    )
    selected = select_multilingual_candidates(
        [focused, complex_case],
        target_tier=4,
        language_history=["java"],
        count=2,
    )

    by_repository = {item["repository"]: item for item in selected}
    assert by_repository["org/focused"]["human_equivalent_workers"] == 2
    assert by_repository["org/focused"]["private_count"] == 20
    assert by_repository["org/complex"]["human_equivalent_workers"] == 12
    assert by_repository["org/complex"]["private_count"] == 120


def test_plan_has_no_lesson_promotion_or_merge_authority() -> None:
    plan = plan_curriculum_round(
        candidates=[_candidate("org/repo", "julia", changed_files=3, changed_lines=100)],
        current_tier=0,
        recent_results=[],
        language_history=[],
        count=1,
    )

    assert plan["authority"] == {
        "may_promote_lessons": False,
        "may_merge": False,
        "final_verdict": "Sergeant",
    }
    assert plan["planned_private_count"] == 20
