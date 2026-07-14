from __future__ import annotations

from types import SimpleNamespace

import pytest

from main_review.github_diff_fetch import fetch_pr_diff_live
from main_review.github_live_fetch import GitHubFetchError


def test_fetch_pr_diff_live_rejects_bad_repository():
    with pytest.raises(GitHubFetchError):
        fetch_pr_diff_live("badrepo", 12)


def test_fetch_pr_diff_live_parses_verified_metadata_and_paginated_files(monkeypatch):
    calls: list[str] = []

    def fake_request_json(url: str, token: str | None, **kwargs):
        calls.append(url)
        return SimpleNamespace(
            payload={
                "number": 12,
                "state": "open",
                "base": {"ref": "main", "sha": "base123", "repo": {"full_name": "owner/repo", "private": False}},
                "head": {"ref": "feature", "sha": "head456", "repo": {"full_name": "fork/repo", "private": False}},
            },
            headers={},
            status=200,
        )

    def fake_fetch_pages(first_url: str, token: str | None, **kwargs):
        calls.append(first_url)
        return ([{
            "filename": "src/app.py",
            "status": "modified",
            "patch": "@@ -1 +1 @@\n-old\n+new",
            "additions": 1,
            "deletions": 1,
        }], [{"method": "GET", "url": first_url, "status": 200, "page": 1, "item_count": 1}], [{}])

    monkeypatch.setattr("main_review.github_diff_fetch._request_json", fake_request_json)
    monkeypatch.setattr("main_review.github_diff_fetch._fetch_pages", fake_fetch_pages)

    result = fetch_pr_diff_live("owner/repo", 12, token="token")

    assert result.repository == "owner/repo"
    assert result.pr_number == 12
    assert result.base_sha == "base123"
    assert result.head_sha == "head456"
    assert result.files[0].filename == "src/app.py"
    assert result.files[0].patch.startswith("@@")
    assert len(calls) == 2
    assert all(item["method"] == "GET" for item in result.request_evidence)
