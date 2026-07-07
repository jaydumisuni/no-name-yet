from __future__ import annotations

import json

from main_review.battle_tests import compare_battle_fixture, validate_battle_fixture, validate_battle_fixtures


def test_validate_battle_fixture_accepts_valid_fixture(tmp_path):
    fixture = tmp_path / "case.json"
    fixture.write_text(
        json.dumps(
            {
                "repository": "owner/repo",
                "pull_request": 12,
                "url": "https://github.com/owner/repo/pull/12",
                "title": "Example PR",
                "outcome": "merged",
                "review_signals": ["overlapping tests"],
                "expected_sergeant_findings": ["Duplicate tests should be removed or parameterized."],
                "expected_initial_verdict": "NEEDS WORK",
                "expected_final_verdict": "PASS",
            }
        ),
        encoding="utf-8",
    )

    result = validate_battle_fixture(fixture)

    assert result.status == "valid"
    assert result.fixture_id == "owner/repo#12"
    assert result.issues == []


def test_validate_battle_fixture_rejects_missing_fields(tmp_path):
    fixture = tmp_path / "case.json"
    fixture.write_text('{"repository": "owner/repo"}', encoding="utf-8")

    result = validate_battle_fixture(fixture)

    assert result.status == "invalid"
    assert "missing required field: pull_request" in result.issues
    assert "pull_request must be an integer" in result.issues


def test_compare_battle_fixture_matches_review_signals_to_findings(tmp_path):
    fixture = tmp_path / "case.json"
    fixture.write_text(
        json.dumps(
            {
                "repository": "owner/repo",
                "pull_request": 12,
                "url": "https://github.com/owner/repo/pull/12",
                "title": "Example PR",
                "outcome": "merged",
                "review_signals": ["overlapping tests", "approved after changes"],
                "expected_sergeant_findings": ["Duplicate tests should be removed or parameterized."],
                "expected_initial_verdict": "NEEDS WORK",
                "expected_final_verdict": "PASS",
            }
        ),
        encoding="utf-8",
    )

    result = compare_battle_fixture(fixture)

    assert result.status == "passed"
    assert result.signal_count == 2
    assert result.matched_signal_count == 2
    assert result.referenced_finding_count == 1
    assert result.issues == []


def test_compare_battle_fixture_rejects_unmatched_review_signal(tmp_path):
    fixture = tmp_path / "case.json"
    fixture.write_text(
        json.dumps(
            {
                "repository": "owner/repo",
                "pull_request": 12,
                "url": "https://github.com/owner/repo/pull/12",
                "title": "Example PR",
                "outcome": "merged",
                "review_signals": ["unmapped reviewer note"],
                "expected_sergeant_findings": ["Duplicate tests should be removed or parameterized."],
                "expected_initial_verdict": "NEEDS WORK",
                "expected_final_verdict": "PASS",
            }
        ),
        encoding="utf-8",
    )

    result = compare_battle_fixture(fixture)

    assert result.status == "failed"
    assert "review signal has no computed Sergeant comparison match" in result.issues[0]


def test_validate_battle_fixtures_reports_verified_for_committed_cases():
    payload = validate_battle_fixtures(__import__("pathlib").Path("."))

    assert payload["status"] == "verified"
    assert payload["fixture_count"] >= 2
    assert payload["invalid_count"] == 0
    assert payload["review_comparison_status"] == "passed"
    assert payload["review_comparison_failed_count"] == 0
    assert payload["next_actions"] == []
