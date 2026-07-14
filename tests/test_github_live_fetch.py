from __future__ import annotations

import json
from email.message import Message

import pytest

from main_review.cli import main
from main_review.github_live_fetch import GitHubFetchError, fetch_pr_comments_live
from main_review.review_contract import github_comments_to_external_provider


def _pr_payload(repository: str = "owner/repo", pr_number: int = 12, *, private: bool = False) -> dict:
    return {
        "number": pr_number,
        "state": "open",
        "draft": False,
        "html_url": f"https://github.com/{repository}/pull/{pr_number}",
        "base": {"ref": "main", "sha": "base-sha", "repo": {"full_name": repository, "private": private}},
        "head": {"ref": "feature", "sha": "head-sha", "repo": {"full_name": "fork/repo", "private": False}},
    }


def _fake_classic_token() -> str:
    return "ghp_" + ("a" * 26)


class _FakeResponse:
    def __init__(self, payload: object, *, url: str, headers: dict[str, str] | None = None, status: int = 200) -> None:
        self.payload = payload
        self.url = url
        self.status = status
        message = Message()
        for key, value in (headers or {}).items():
            message[key] = value
        self.headers = message

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_live_github_fetch_verifies_pr_and_uses_get_only(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, str | None]] = []

    def fake_urlopen(request, timeout: int):  # type: ignore[no-untyped-def]
        calls.append((request.full_url, request.get_method(), request.headers.get("Authorization")))
        payload = _pr_payload() if request.full_url.endswith("/pulls/12") else [{"body": "Check this edge case", "user": {"login": "reviewer"}}]
        return _FakeResponse(payload, url=request.full_url, headers={"X-OAuth-Scopes": "read:org"})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = fetch_pr_comments_live("owner/repo", 12, token="read-token", base_url="https://example.test", allowed_hosts=["example.test"])

    assert result.repository == "owner/repo"
    assert result.pr_number == 12
    assert result.pull_request["base"]["repo"]["full_name"] == "owner/repo"
    assert len(result.issue_comments) == 1
    assert len(result.review_comments) == 1
    assert all(method == "GET" for _, method, _ in calls)
    assert all(auth == "Bearer read-token" for _, _, auth in calls)
    assert calls[0][0].endswith("/repos/owner/repo/pulls/12")
    assert calls[1][0].endswith("/repos/owner/repo/issues/12/comments?per_page=100")
    assert calls[2][0].endswith("/repos/owner/repo/pulls/12/comments?per_page=100")
    assert result.token_scope_assessment["scope_evidence"] == "verified-read-only"


def test_live_github_fetch_follows_same_host_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_urlopen(request, timeout: int):  # type: ignore[no-untyped-def]
        calls.append(request.full_url)
        if request.full_url.endswith("/pulls/12"):
            return _FakeResponse(_pr_payload(), url=request.full_url)
        if "/issues/12/comments" in request.full_url and "page=2" not in request.full_url:
            headers = {"Link": '<https://example.test/repos/owner/repo/issues/12/comments?per_page=100&page=2>; rel="next"'}
            return _FakeResponse([{"id": 1, "body": "first"}], url=request.full_url, headers=headers)
        if "/issues/12/comments" in request.full_url:
            return _FakeResponse([{"id": 2, "body": "second"}], url=request.full_url)
        return _FakeResponse([], url=request.full_url)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = fetch_pr_comments_live("owner/repo", 12, base_url="https://example.test", allowed_hosts=["example.test"])

    assert [item["id"] for item in result.issue_comments] == [1, 2]
    assert len(result.request_evidence) == 4
    assert any("page=2" in url for url in calls)


def test_live_github_fetch_rejects_redirected_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout: int):  # type: ignore[no-untyped-def]
        return _FakeResponse(_pr_payload(), url="https://evil.test/stolen")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(GitHubFetchError, match="redirected"):
        fetch_pr_comments_live("owner/repo", 12, base_url="https://example.test", allowed_hosts=["example.test"])


def test_live_github_fetch_rejects_bad_inputs_hosts_spoofing_and_private_repos(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(GitHubFetchError):
        fetch_pr_comments_live("not-a-repo", 1)
    with pytest.raises(GitHubFetchError):
        fetch_pr_comments_live("owner/repo", 0)
    with pytest.raises(GitHubFetchError, match="not explicitly trusted"):
        fetch_pr_comments_live("owner/repo", 1, base_url="https://metadata.internal")

    def spoofed_urlopen(request, timeout: int):  # type: ignore[no-untyped-def]
        return _FakeResponse(_pr_payload("other/repo"), url=request.full_url)

    monkeypatch.setattr("urllib.request.urlopen", spoofed_urlopen)
    with pytest.raises(GitHubFetchError, match="base repository"):
        fetch_pr_comments_live("owner/repo", 12, base_url="https://example.test", allowed_hosts=["example.test"])

    def private_urlopen(request, timeout: int):  # type: ignore[no-untyped-def]
        return _FakeResponse(_pr_payload(private=True) if request.full_url.endswith("/pulls/12") else [], url=request.full_url)

    monkeypatch.setattr("urllib.request.urlopen", private_urlopen)
    with pytest.raises(GitHubFetchError, match="Private-repository"):
        fetch_pr_comments_live("owner/repo", 12, base_url="https://example.test", allowed_hosts=["example.test"])


def test_live_github_fetch_rejects_advertised_write_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout: int):  # type: ignore[no-untyped-def]
        payload = _pr_payload() if request.full_url.endswith("/pulls/12") else []
        return _FakeResponse(payload, url=request.full_url, headers={"X-OAuth-Scopes": "repo, read:org"})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(GitHubFetchError, match="write-capable"):
        fetch_pr_comments_live("owner/repo", 12, token=_fake_classic_token(), base_url="https://example.test", allowed_hosts=["example.test"])


def test_live_github_fetch_redacts_secrets_and_proof_omits_bodies(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = _fake_classic_token()

    def fake_urlopen(request, timeout: int):  # type: ignore[no-untyped-def]
        payload = _pr_payload() if request.full_url.endswith("/pulls/12") else [{"id": 1, "body": f"leaked {secret}"}]
        return _FakeResponse(payload, url=request.full_url)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = fetch_pr_comments_live("owner/repo", 12, base_url="https://example.test", allowed_hosts=["example.test"])
    proof = result.proof_dict()
    proof_text = json.dumps(proof)

    assert secret not in result.all_comments[0]["body"]
    assert result.secret_redactions == 2
    assert "all_comments" not in proof
    assert '"body":' not in proof_text
    assert secret not in proof_text
    assert proof["claims"]["repository_identity_verified"] is True
    assert proof["claims"]["redirects_refused"] is True
    assert proof["claims"]["get_only"] is True


def test_live_github_comments_convert_to_external_provider() -> None:
    provider = github_comments_to_external_provider({
        "repository": "owner/repo",
        "pr_number": 12,
        "source": "live-github-api",
        "pull_request": {"base": {"sha": "base-sha"}},
        "token_scope_assessment": {"scope_evidence": "anonymous"},
        "all_comments": [
            {"body": "CodeRabbit: possible regression", "path": "src/app.py", "user": {"login": "coderabbitai"}, "html_url": "https://example.test/comment"},
            {"body": ""},
        ],
    })

    assert provider["name"] == "github-live-comments"
    assert provider["verdict"] == "COMMENT"
    assert provider["findings"][0]["path"] == "src/app.py"
    assert provider["metadata"]["repository"] == "owner/repo"
    assert provider["metadata"]["pull_request"]["base"]["sha"] == "base-sha"


def test_live_github_comments_cli_uses_environment_token_and_writes_proof(tmp_path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("TEST_GITHUB_TOKEN", "read-token")

    def fake_urlopen(request, timeout: int):  # type: ignore[no-untyped-def]
        payload = _pr_payload() if request.full_url.endswith("/pulls/12") else []
        return _FakeResponse(payload, url=request.full_url, headers={"X-OAuth-Scopes": "read:org"})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    proof_path = tmp_path / "live-proof.json"
    code = main([
        "live-github-comments",
        "owner/repo",
        "12",
        "--base-url",
        "https://example.test",
        "--allowed-host",
        "example.test",
        "--token-env",
        "TEST_GITHUB_TOKEN",
        "--proof-only",
        "--proof-output",
        str(proof_path),
    ])

    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads(proof_path.read_text(encoding="utf-8"))
    assert printed == saved
    assert saved["proof_version"] == "sergeant.live-github-proof.v1"
    assert saved["token_scope_assessment"]["scope_evidence"] == "verified-read-only"
