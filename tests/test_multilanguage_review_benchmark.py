from __future__ import annotations

from pathlib import Path

from main_review.review_benchmark import load_cases, run_blind_benchmark


SUITE = Path(__file__).resolve().parents[1] / "review-benchmarks" / "multilanguage"


def test_multilanguage_suite_has_defect_and_clean_control_for_each_language() -> None:
    cases = {payload["id"] for _, payload in load_cases(SUITE)}

    assert cases == {
        "typescript-command-injection",
        "typescript-command-clean",
        "go-unsafe-sql",
        "go-parameterized-sql",
        "rust-path-traversal",
        "rust-contained-path",
        "java-admin-authorization",
        "java-admin-authorized",
        "csharp-shared-counter",
        "csharp-atomic-counter",
        "ruby-nested-loop",
        "ruby-linear-loop",
    }


def test_model_free_multilanguage_suite_is_exact() -> None:
    result = run_blind_benchmark(
        SUITE,
        mode="deterministic",
        minimum_precision=1.0,
        minimum_recall=1.0,
    )

    assert result["passed"] is True
    assert result["case_count"] == 12
    assert result["expected_finding_count"] == 9
    assert result["true_positive_count"] == 9
    assert result["false_positive_count"] == 0
    assert result["false_negative_count"] == 0
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["verdict_accuracy"] == 1.0
    assert result["model_call_count"] == 0
    assert result["distinct_models"] == []
