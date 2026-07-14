from __future__ import annotations

import json
from dataclasses import dataclass

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


@dataclass(frozen=True)
class FakeComments:
    all_comments: list[dict[str, str]]


def _fake_comments(repository: str, pr_number: int, **kwargs):
    return FakeComments([])


def test_run_battle_comparison_scores_expected_matches(tmp_path, monkeypatch):
    fixture = tmp_path / "case.json"
    fixture.write_text(
        json.dumps({
            "repository": "owner/repo",
            "pull_request": 12,
            "url": "https://github.com/owner/repo/pull/12",
            "title": "Example PR",
            "outcome": "merged",
            "review_signals": ["test clarity"],
            "expected_sergeant_findings": ["Duplicate tests should be removed or parameterized."],
            "expected_initial_verdict": "NEEDS WORK",
            "expected_final_verdict": "PASS",
        }),
        encoding="utf-8",
    )

    def fake_fetch(repository: str, pr_number: int, **kwargs):
        return FakeDiff(
            repository=repository,
            pr_number=pr_number,
            base_sha="base",
            head_sha="head",
            files=[FakeFile("tests/test_app.py", "@@\n+def test_post_named_tempfile():\n+    NamedTemporaryFile()\n+def test_post_named_tempfile():\n+    NamedTemporaryFile()\n")],
        )

    monkeypatch.setattr("main_review.battle_compare.fetch_pr_diff_live", fake_fetch)
    monkeypatch.setattr("main_review.battle_compare.fetch_pr_comments_live", _fake_comments)
    result = run_battle_comparison(fixture)

    assert result.files_reviewed == ["tests/test_app.py"]
    assert result.agreement_rate == 1.0
    assert result.expected_matches[0].matched is True
    assert result.false_positive_candidates == []


def test_run_battle_comparison_reports_missed_without_repo_noise(tmp_path, monkeypatch):
    fixture = tmp_path / "case.json"
    fixture.write_text(
        json.dumps({
            "repository": "owner/repo",
            "pull_request": 12,
            "url": "https://github.com/owner/repo/pull/12",
            "title": "Example PR",
            "outcome": "merged",
            "review_signals": ["architecture"],
            "expected_sergeant_findings": ["Architecture lifecycle risk should be reviewed."],
            "expected_initial_verdict": "NEEDS WORK",
            "expected_final_verdict": "PASS",
        }),
        encoding="utf-8",
    )

    def fake_fetch(repository: str, pr_number: int, **kwargs):
        return FakeDiff(repository, pr_number, "base", "head", [FakeFile("src/app.py", "@@\n+plain change")])

    monkeypatch.setattr("main_review.battle_compare.fetch_pr_diff_live", fake_fetch)
    monkeypatch.setattr("main_review.battle_compare.fetch_pr_comments_live", _fake_comments)
    result = run_battle_comparison(fixture)
    payload = result.to_dict()

    assert result.agreement_rate == 0.0
    assert payload["missed_expected_findings"] == ["Architecture lifecycle risk should be reviewed."]
    assert result.false_positive_candidates == []


def test_patch_only_battle_compare_does_not_emit_repo_level_doc_or_test_noise(tmp_path, monkeypatch):
    fixture = tmp_path / "case.json"
    fixture.write_text(
        json.dumps({
            "repository": "owner/repo",
            "pull_request": 12,
            "url": "https://github.com/owner/repo/pull/12",
            "title": "Example PR",
            "outcome": "merged",
            "review_signals": ["review"],
            "expected_sergeant_findings": ["Follow-up review feedback should be tracked before treating the change as final."],
            "expected_initial_verdict": "NEEDS WORK",
            "expected_final_verdict": "PASS_WITH_WATCH",
        }),
        encoding="utf-8",
    )

    def fake_fetch(repository: str, pr_number: int, **kwargs):
        return FakeDiff(repository, pr_number, "base", "head", [FakeFile("src/app.py", "@@\n+plain change")])

    monkeypatch.setattr("main_review.battle_compare.fetch_pr_diff_live", fake_fetch)
    monkeypatch.setattr("main_review.battle_compare.fetch_pr_comments_live", _fake_comments)
    result = run_battle_comparison(fixture)

    assert all("No documentation files were detected" not in text for text in result.sergeant_finding_texts)
    assert all("Source files exist but no tests were detected" not in text for text in result.sergeant_finding_texts)
