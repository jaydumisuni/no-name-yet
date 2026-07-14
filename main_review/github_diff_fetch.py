"""Fetch validated pull-request diff metadata and patches from GitHub.

The fetch is GET-only, host-allowlisted, pagination-bounded, repository-identity
checked, and never executes the returned patch text.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from main_review.github_live_fetch import (
    GitHubFetchError,
    _fetch_pages,
    _request_json,
    _verify_pr_identity,
)
from main_review.production_hardening import HardeningError, configured_github_hosts, validate_github_base_url, validate_repository_slug


@dataclass(frozen=True)
class PullRequestFile:
    filename: str
    status: str
    patch: str | None
    additions: int
    deletions: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "status": self.status,
            "patch": self.patch,
            "additions": self.additions,
            "deletions": self.deletions,
        }


@dataclass(frozen=True)
class PullRequestDiff:
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    files: list[PullRequestFile]
    request_evidence: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "pr_number": self.pr_number,
            "base_sha": self.base_sha,
            "head_sha": self.head_sha,
            "files": [file.to_dict() for file in self.files],
            "request_evidence": self.request_evidence,
        }


def fetch_pr_diff_live(
    repository: str,
    pr_number: int,
    *,
    token: str | None = None,
    base_url: str = "https://api.github.com",
    allowed_hosts: Iterable[str] = (),
    allow_insecure_loopback: bool = False,
    allow_private: bool = False,
    max_pages: int = 20,
) -> PullRequestDiff:
    """Fetch verified PR metadata and all paginated file patches."""

    try:
        repository = validate_repository_slug(repository)
        base_url = validate_github_base_url(
            base_url,
            allowed_hosts=allowed_hosts,
            allow_insecure_loopback=allow_insecure_loopback,
        )
    except HardeningError as error:
        raise GitHubFetchError(str(error)) from error
    if pr_number <= 0:
        raise GitHubFetchError(f"pr_number must be positive, got: {pr_number!r}")

    trusted_hosts = configured_github_hosts(allowed_hosts)
    pr_url = f"{base_url}/repos/{repository}/pulls/{pr_number}"
    pr_response = _request_json(
        pr_url,
        token,
        allowed_hosts=trusted_hosts,
        allow_insecure_loopback=allow_insecure_loopback,
    )
    identity = _verify_pr_identity(pr_response.payload, repository, pr_number, allow_private=allow_private)
    base_ref = identity.get("base", {})
    head_ref = identity.get("head", {})
    base_sha = base_ref.get("sha") if isinstance(base_ref, dict) else None
    head_sha = head_ref.get("sha") if isinstance(head_ref, dict) else None
    if not isinstance(base_sha, str) or not base_sha:
        raise GitHubFetchError(f"PR payload from {pr_url} missing base sha")
    if not isinstance(head_sha, str) or not head_sha:
        raise GitHubFetchError(f"PR payload from {pr_url} missing head sha")

    files_url = f"{base_url}/repos/{repository}/pulls/{pr_number}/files?per_page=100"
    files_data, page_evidence, _ = _fetch_pages(
        files_url,
        token,
        base_url=base_url,
        repository=repository,
        pr_number=pr_number,
        allowed_hosts=trusted_hosts,
        allow_insecure_loopback=allow_insecure_loopback,
        max_pages=max_pages,
    )

    files: list[PullRequestFile] = []
    for item in files_data:
        filename = item.get("filename")
        if not isinstance(filename, str) or not filename:
            continue
        files.append(
            PullRequestFile(
                filename=filename,
                status=str(item.get("status", "modified")),
                patch=item.get("patch") if isinstance(item.get("patch"), str) else None,
                additions=int(item.get("additions", 0) or 0),
                deletions=int(item.get("deletions", 0) or 0),
            )
        )

    return PullRequestDiff(
        repository=repository,
        pr_number=pr_number,
        base_sha=base_sha,
        head_sha=head_sha,
        files=files,
        request_evidence=[{"method": "GET", "url": pr_url, "status": pr_response.status, "page": 1, "item_count": 1}, *page_evidence],
    )
