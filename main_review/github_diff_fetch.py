"""Fetch real pull request diff metadata and file patches from GitHub.

This module is a read-only companion to ``github_live_fetch``. It performs
GET-only API calls and raises on failure instead of fabricating an empty diff.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from main_review.github_live_fetch import GitHubFetchError, _get_json


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "pr_number": self.pr_number,
            "base_sha": self.base_sha,
            "head_sha": self.head_sha,
            "files": [file.to_dict() for file in self.files],
        }


def fetch_pr_diff_live(
    repository: str,
    pr_number: int,
    *,
    token: str | None = None,
    base_url: str = "https://api.github.com",
) -> PullRequestDiff:
    """Fetch PR metadata and per-file patches through the GitHub API.

    Raises ``GitHubFetchError`` on invalid input or unexpected API payloads.
    The function is intentionally read-only and never executes fetched content.
    """
    if "/" not in repository:
        raise GitHubFetchError(f'repository must be "owner/name", got: {repository!r}')

    pr_url = f"{base_url}/repos/{repository}/pulls/{pr_number}"
    pr_data = _get_json(pr_url, token)
    if not isinstance(pr_data, dict):
        raise GitHubFetchError(f"Unexpected PR payload shape from {pr_url}")

    base = pr_data.get("base")
    head = pr_data.get("head")
    if not isinstance(base, dict) or not isinstance(head, dict):
        raise GitHubFetchError(f"PR payload from {pr_url} missing base/head objects")

    base_sha = base.get("sha")
    head_sha = head.get("sha")
    if not isinstance(base_sha, str) or not base_sha:
        raise GitHubFetchError(f"PR payload from {pr_url} missing base sha")
    if not isinstance(head_sha, str) or not head_sha:
        raise GitHubFetchError(f"PR payload from {pr_url} missing head sha")

    files_url = f"{base_url}/repos/{repository}/pulls/{pr_number}/files?per_page=100"
    files_data = _get_json(files_url, token)
    if not isinstance(files_data, list):
        raise GitHubFetchError(f"Unexpected files payload shape from {files_url}")

    files: list[PullRequestFile] = []
    for item in files_data:
        if not isinstance(item, dict) or "filename" not in item:
            continue
        filename = item["filename"]
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
    )
