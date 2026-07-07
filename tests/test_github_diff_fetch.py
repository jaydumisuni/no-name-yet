from __future__ import annotations

import pytest

from main_review.github_diff_fetch import fetch_pr_diff_live
from main_review.github_live_fetch import GitHubFetchError


def test_fetch_pr_diff_live_rejects_bad_repository():
    with pytest.raises(GitHubFetchError):
        fetch_pr_diff_live("badrepo", 12)


def test_fetch_pr_diff_live_parses_metadata_and_files(monkeypatch):
    calls: list[str] = []

    def fake_get_json(url: str, token: str | None):
        calls.append(url)
        if url.endswith("/pulls/12"):
            return {"base": {"sha": "base123"}, "head": {"sha": "head456"}}
        if url.endswith("/pulls/12/files?per_page=100"):
            return [
                {
                    "filename": "src/app.py",
                    "status": "modified",
                    "patch": "@@ -1 +1 @@\n-old\n+new",
                    "additions": 1,
                    "deletions": 1,
                }
            ]
        raise AssertionError(url)

    monkeypatch.setattr("main_review.github_diff_fetch._get_json", fake_get_json)

    result = fetch_pr_diff_live("owner/repo", 12, token="token")

    assert result.repository == "owner/repo"
    assert result.pr_number == 12
    assert result.base_sha == "base123"
    assert result.head_sha == "head456"
    assert result.files[0].filename == "src/app.py"
    assert result.files[0].patch.startswith("@@")
    assert len(calls) == 2
