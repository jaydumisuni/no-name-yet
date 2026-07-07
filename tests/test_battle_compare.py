from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from main_review.battle_compare import run_battle_comparison


@dataclass(frozen=True)
class FakeFile:
    filename: str
    patch: str


@dataclass(frozen=True)
class FakeDiff:
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    files: list[FakeFile]


def test_run_battle_comparison_scores_expected_matches(tmp_path, monkeypatch):
    fixture = tmp_path / "case.json"
    fixture.write_text(
        json.dumps(
            {
                "repository": "owner/repo",
                "pull_request": 12,
                "url": "https://github.com/owner/repo/pull/12",
                "title": "Example PR",
                "outcome": "merged",
                "review_signals": ["test clarity"],
                "expected_sergeant_findings": ["Duplicate tests should be removed or parameterized."],
                "expected_initial_verdict": "NEEDS WORK",
                "expected_final_verdict": "PASS",
            }
        ),
        encoding="utf-8",
    )

    def fake_fetch(repository: str, pr_number: int, *, token=None, base_url="https://api.github.com"):
        return FakeDiff(
            repository=repository,
            pr_number=pr_number,
            base_sha="base",
            head_sha="head",
            files=[FakeFile("tests/test_app.py", "@@\n+duplicate tests should be parameterized")],
        )

    def fake_review(root: Path):
        return {
            "verdict": {
                "major_findings": [
                    {
                        "category": "tests",
                        "message": "Duplicate tests should be removed or parameterized.",
                        "path": "tests/test_app.py",
                        "severity": "major",
                    }
                ]
            }
        }

    monkeypatch.setattr("main_review.battle_compare.fetch_pr_diff_live", fake_fetch)
    monkeypatch.setattr("main_review.battle_compare.review_repository", fake_review)

    result = run_battle_comparison(fixture)

    assert result.files_reviewed == ["tests/test_app.py"]
    assert result.agreement_rate == 1.0
    assert result.expected_matches[0].matched is True
    assert result.false_positive_candidates == []


def test_run_battle_comparison_reports_missed_and_extra_findings(tmp_path, monkeypatch):
    fixture = tmp_path / "case.json"
    fixture.write_text(
        json.dumps(
            {
                "repository": "owner/repo",
                "pull_request": 12,
                "url": "https://github.com/owner/repo/pull/12",
                "title": "Example PR",
                "outcome": "merged",
                "review_signals": ["architecture"],
                "expected_sergeant_findings": ["Architecture lifecycle risk should be reviewed."],
                "expected_initial_verdict": "NEEDS WORK",
                "expected_final_verdict": "PASS",
            }
        ),
        encoding="utf-8",
    )

    def fake_fetch(repository: str, pr_number: int, *, token=None, base_url="https://api.github.com"):
        return FakeDiff(repository, pr_number, "base", "head", [FakeFile("src/app.py", "@@\n+change")])

    def fake_review(root: Path):
        return {"verdict": {"minor_findings": [{"message": "style note only", "path": "src/app.py"}]}}

    monkeypatch.setattr("main_review.battle_compare.fetch_pr_diff_live", fake_fetch)
    monkeypatch.setattr("main_review.battle_compare.review_repository", fake_review)

    result = run_battle_comparison(fixture)
    payload = result.to_dict()

    assert result.agreement_rate == 0.0
    assert payload["missed_expected_findings"] == ["Architecture lifecycle risk should be reviewed."]
    assert result.false_positive_candidates == ["style note only src/app.py"]
