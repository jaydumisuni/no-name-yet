from __future__ import annotations

import json

import pytest

from main_review.cli import main
from main_review.github_live_fetch import GitHubFetchError, fetch_pr_comments_live
from main_review.review_contract import github_comments_to_external_provider


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_live_github_fetch_uses_read_only_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_urlopen(request, timeout: int):  # type: ignore[no-untyped-def]
        calls.append((request.full_url, request.get_method()))
        return _FakeResponse([{"body": "Check this edge case", "user": {"login": "reviewer"}}])

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = fetch_pr_comments_live("owner/repo", 12, token="read-token", base_url="https://example.test")

    assert result.repository == "owner/repo"
    assert result.pr_number == 12
    assert len(result.issue_comments) == 1
    assert len(result.review_comments) == 1
    assert all(method == "GET" for _, method in calls)
    assert calls[0][0].endswith("/repos/owner/repo/issues/12/comments")
    assert calls[1][0].endswith("/repos/owner/repo/pulls/12/comments")


def test_live_github_fetch_rejects_bad_inputs() -> None:
    with pytest.raises(GitHubFetchError):
        fetch_pr_comments_live("not-a-repo", 1)
    with pytest.raises(GitHubFetchError):
        fetch_pr_comments_live("owner/repo", 0)


def test_live_github_comments_convert_to_external_provider() -> None:
    provider = github_comments_to_external_provider({
        "repository": "owner/repo",
        "pr_number": 12,
        "source": "live-github-api",
        "all_comments": [
            {"body": "CodeRabbit: possible regression", "path": "src/app.py", "user": {"login": "coderabbitai"}, "html_url": "https://example.test/comment"},
            {"body": ""},
        ],
    })

    assert provider["name"] == "github-live-comments"
    assert provider["verdict"] == "COMMENT"
    assert provider["findings"][0]["path"] == "src/app.py"
    assert provider["metadata"]["repository"] == "owner/repo"


def test_live_github_comments_cli_runs_with_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout: int):  # type: ignore[no-untyped-def]
        return _FakeResponse([])

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert main(["live-github-comments", "owner/repo", "12", "--base-url", "https://example.test"]) == 0
