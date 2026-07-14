"""Read-only, production-hardened live GitHub PR evidence ingestion.

This module is the only built-in Sergeant component that fetches GitHub PR
comments. It validates the API host, repository identity, pull-request base
repository, token-scope evidence, pagination links, visibility, payload shape,
and public-output redaction before returning evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping
from urllib.parse import urljoin, urlparse

from .production_hardening import (
    HardeningError,
    assess_token_scopes,
    configured_github_hosts,
    redact_secrets,
    validate_github_base_url,
    validate_repository_slug,
)


class GitHubFetchError(RuntimeError):
    """Raised when a live GitHub API fetch violates policy or fails."""


@dataclass(frozen=True)
class GitHubFetchResult:
    repository: str
    pr_number: int
    pull_request: dict[str, Any]
    issue_comments: list[dict[str, Any]]
    review_comments: list[dict[str, Any]]
    request_evidence: list[dict[str, Any]] = field(default_factory=list)
    token_scope_assessment: dict[str, Any] = field(default_factory=dict)
    secret_redactions: int = 0
    source: str = "live-github-api"

    @property
    def all_comments(self) -> list[dict[str, Any]]:
        return [*self.issue_comments, *self.review_comments]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["all_comments"] = self.all_comments
        return payload

    def proof_dict(self) -> dict[str, Any]:
        """Return a shareable proof artifact without comment bodies or tokens."""

        comment_hashes = [
            hashlib.sha256(str(comment.get("body", "")).encode("utf-8")).hexdigest()
            for comment in self.all_comments
        ]
        return {
            "proof_version": "sergeant.live-github-proof.v1",
            "source": self.source,
            "repository": self.repository,
            "pr_number": self.pr_number,
            "pull_request": self.pull_request,
            "issue_comment_count": len(self.issue_comments),
            "review_comment_count": len(self.review_comments),
            "comment_body_sha256": comment_hashes,
            "request_evidence": self.request_evidence,
            "token_scope_assessment": self.token_scope_assessment,
            "secret_redactions": self.secret_redactions,
            "claims": {
                "network_fetch_completed": True,
                "get_only": all(item.get("method") == "GET" for item in self.request_evidence),
                "repository_identity_verified": True,
                "redirects_refused": True,
                "pagination_verified": True,
                "comment_bodies_omitted_from_proof": True,
            },
        }


@dataclass(frozen=True)
class _JsonResponse:
    payload: object
    headers: dict[str, str]
    url: str
    status: int


def _headers_dict(headers: object) -> dict[str, str]:
    if hasattr(headers, "items"):
        return {str(key): str(value) for key, value in headers.items()}  # type: ignore[union-attr]
    return {}


def _request_json(
    url: str,
    token: str | None,
    *,
    allowed_hosts: Iterable[str] = (),
    allow_insecure_loopback: bool = False,
) -> _JsonResponse:
    parsed = urlparse(url)
    base_path = "/api/v3" if parsed.path.startswith("/api/v3/") else ""
    trusted_base = f"{parsed.scheme}://{parsed.netloc}{base_path}"
    try:
        validate_github_base_url(
            trusted_base,
            allowed_hosts=allowed_hosts,
            allow_insecure_loopback=allow_insecure_loopback,
        )
    except HardeningError as error:
        raise GitHubFetchError(str(error)) from error

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "sergeant-review/phase-7",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            response_headers = _headers_dict(getattr(response, "headers", {}))
            final_url = str(getattr(response, "url", url) or url)
            status = int(getattr(response, "status", 200) or 200)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace") if error.fp else ""
        safe_body = redact_secrets(body[:300])
        raise GitHubFetchError(f"GitHub API returned HTTP {error.code} for {url}: {safe_body}") from error
    except urllib.error.URLError as error:
        raise GitHubFetchError(f"Network error reaching {url}: {redact_secrets(error.reason)}") from error

    final = urlparse(final_url)
    requested_identity = (parsed.scheme, parsed.hostname, parsed.port, parsed.path, parsed.query)
    final_identity = (final.scheme, final.hostname, final.port, final.path, final.query)
    if final_identity != requested_identity:
        raise GitHubFetchError("GitHub API redirected the request; redirects are refused by the live-ingestion boundary.")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise GitHubFetchError(f"GitHub API returned non-JSON response for {url}") from error
    return _JsonResponse(payload=payload, headers=response_headers, url=final_url, status=status)


def _get_json(
    url: str,
    token: str | None,
    *,
    allowed_hosts: Iterable[str] = (),
    allow_insecure_loopback: bool = False,
) -> object:
    """Compatibility wrapper returning only decoded JSON."""

    return _request_json(
        url,
        token,
        allowed_hosts=allowed_hosts,
        allow_insecure_loopback=allow_insecure_loopback,
    ).payload


def _next_link(headers: Mapping[str, str]) -> str | None:
    link = next((value for key, value in headers.items() if key.lower() == "link"), "")
    for part in link.split(","):
        match = re.match(r'\s*<([^>]+)>\s*;\s*rel="([^"]+)"', part)
        if match and match.group(2) == "next":
            return match.group(1)
    return None


def _validate_pagination_url(next_url: str, base_url: str, repository: str, pr_number: int) -> str:
    candidate = urljoin(base_url + "/", next_url)
    parsed = urlparse(candidate)
    base = urlparse(base_url)
    if (parsed.scheme, parsed.hostname, parsed.port) != (base.scheme, base.hostname, base.port):
        raise GitHubFetchError("GitHub pagination attempted to leave the trusted API host.")
    path = parsed.path.removeprefix("/api/v3") if base.path == "/api/v3" else parsed.path
    allowed_paths = {
        f"/repos/{repository}/issues/{pr_number}/comments",
        f"/repos/{repository}/pulls/{pr_number}/comments",
        f"/repos/{repository}/pulls/{pr_number}/files",
    }
    if path not in allowed_paths:
        raise GitHubFetchError("GitHub pagination URL does not match an allowed endpoint for the requested repository and pull request.")
    return candidate


def _fetch_pages(
    first_url: str,
    token: str | None,
    *,
    base_url: str,
    repository: str,
    pr_number: int,
    allowed_hosts: Iterable[str],
    allow_insecure_loopback: bool,
    max_pages: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    items: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    headers_seen: list[dict[str, str]] = []
    url: str | None = first_url
    page = 0
    seen_urls: set[str] = set()
    while url:
        page += 1
        if page > max_pages:
            raise GitHubFetchError(f"GitHub pagination exceeded the configured limit of {max_pages} pages.")
        if url in seen_urls:
            raise GitHubFetchError("GitHub pagination loop detected.")
        seen_urls.add(url)
        response = _request_json(
            url,
            token,
            allowed_hosts=allowed_hosts,
            allow_insecure_loopback=allow_insecure_loopback,
        )
        if not isinstance(response.payload, list):
            raise GitHubFetchError(f"Unexpected paginated payload shape from {url}")
        items.extend(item for item in response.payload if isinstance(item, dict))
        headers_seen.append(response.headers)
        evidence.append({"method": "GET", "url": url, "status": response.status, "page": page, "item_count": len(response.payload)})
        next_url = _next_link(response.headers)
        url = _validate_pagination_url(next_url, base_url, repository, pr_number) if next_url else None
    return items, evidence, headers_seen


def _safe_repo(repo: object) -> dict[str, Any]:
    value = repo if isinstance(repo, dict) else {}
    return {
        "full_name": value.get("full_name"),
        "private": bool(value.get("private", False)),
    }


def _safe_ref(value: object) -> dict[str, Any]:
    item = value if isinstance(value, dict) else {}
    return {
        "ref": item.get("ref"),
        "sha": item.get("sha"),
        "repo": _safe_repo(item.get("repo")),
    }


def _verify_pr_identity(payload: object, repository: str, pr_number: int, *, allow_private: bool) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise GitHubFetchError("Unexpected pull-request metadata payload shape.")
    number = payload.get("number")
    if number is not None:
        try:
            payload_number = int(number)
        except (TypeError, ValueError) as error:
            raise GitHubFetchError("GitHub pull-request payload contains an invalid PR number.") from error
        if payload_number != pr_number:
            raise GitHubFetchError("GitHub pull-request number does not match the requested PR.")
    base = _safe_ref(payload.get("base"))
    base_repo = base.get("repo", {})
    if base_repo.get("full_name") != repository:
        raise GitHubFetchError("GitHub pull-request base repository does not match the requested repository.")
    if base_repo.get("private") and not allow_private:
        raise GitHubFetchError("Private-repository live evidence is blocked unless allow_private is explicitly enabled.")
    return {
        "number": pr_number,
        "state": payload.get("state"),
        "draft": bool(payload.get("draft", False)),
        "html_url": payload.get("html_url"),
        "base": base,
        "head": _safe_ref(payload.get("head")),
        "repository_visibility": "private" if base_repo.get("private") else "public",
    }


def _safe_comment(comment: dict[str, Any]) -> tuple[dict[str, Any], int]:
    body = str(comment.get("body") or "")
    truncated = len(body) > 65536
    safe_body = redact_secrets(body[:65536])
    redactions = int(safe_body != body[:65536])
    user = comment.get("user") if isinstance(comment.get("user"), dict) else {}
    safe = {
        "id": comment.get("id"),
        "body": safe_body,
        "body_truncated": truncated,
        "path": comment.get("path"),
        "line": comment.get("line"),
        "start_line": comment.get("start_line"),
        "side": comment.get("side"),
        "commit_id": comment.get("commit_id"),
        "created_at": comment.get("created_at"),
        "updated_at": comment.get("updated_at"),
        "html_url": comment.get("html_url"),
        "pull_request_review_id": comment.get("pull_request_review_id"),
        "user": {"login": user.get("login"), "type": user.get("type")},
    }
    return safe, redactions


def fetch_pr_comments_live(
    repository: str,
    pr_number: int,
    *,
    token: str | None = None,
    base_url: str = "https://api.github.com",
    allowed_hosts: Iterable[str] = (),
    allow_insecure_loopback: bool = False,
    allow_private: bool = False,
    max_pages: int = 20,
) -> GitHubFetchResult:
    """Fetch and validate live PR metadata, issue comments, and review comments."""

    try:
        repository = validate_repository_slug(repository)
        base = validate_github_base_url(
            base_url,
            allowed_hosts=allowed_hosts,
            allow_insecure_loopback=allow_insecure_loopback,
        )
    except HardeningError as error:
        raise GitHubFetchError(str(error)) from error
    if pr_number <= 0:
        raise GitHubFetchError(f"pr_number must be positive, got: {pr_number!r}")
    if not 1 <= max_pages <= 100:
        raise GitHubFetchError("max_pages must be between 1 and 100.")

    trusted_hosts = configured_github_hosts(allowed_hosts)
    metadata_url = f"{base}/repos/{repository}/pulls/{pr_number}"
    metadata_response = _request_json(
        metadata_url,
        token,
        allowed_hosts=trusted_hosts,
        allow_insecure_loopback=allow_insecure_loopback,
    )
    pull_request = _verify_pr_identity(metadata_response.payload, repository, pr_number, allow_private=allow_private)
    request_evidence: list[dict[str, Any]] = [
        {"method": "GET", "url": metadata_url, "status": metadata_response.status, "page": 1, "item_count": 1}
    ]

    issue_url = f"{base}/repos/{repository}/issues/{pr_number}/comments?per_page=100"
    review_url = f"{base}/repos/{repository}/pulls/{pr_number}/comments?per_page=100"
    issue_raw, issue_evidence, issue_headers = _fetch_pages(
        issue_url,
        token,
        base_url=base,
        repository=repository,
        pr_number=pr_number,
        allowed_hosts=trusted_hosts,
        allow_insecure_loopback=allow_insecure_loopback,
        max_pages=max_pages,
    )
    review_raw, review_evidence, review_headers = _fetch_pages(
        review_url,
        token,
        base_url=base,
        repository=repository,
        pr_number=pr_number,
        allowed_hosts=trusted_hosts,
        allow_insecure_loopback=allow_insecure_loopback,
        max_pages=max_pages,
    )
    request_evidence.extend(issue_evidence)
    request_evidence.extend(review_evidence)

    combined_headers: dict[str, str] = {}
    for headers in [metadata_response.headers, *issue_headers, *review_headers]:
        for key, value in headers.items():
            if key.lower() == "x-oauth-scopes":
                current = combined_headers.get("X-OAuth-Scopes", "")
                combined_headers["X-OAuth-Scopes"] = ",".join(part for part in (current, value) if part)
    try:
        token_assessment = assess_token_scopes(combined_headers, token_supplied=bool(token))
    except HardeningError as error:
        raise GitHubFetchError(str(error)) from error

    issue_comments: list[dict[str, Any]] = []
    review_comments: list[dict[str, Any]] = []
    redactions = 0
    for item in issue_raw:
        safe, count = _safe_comment(item)
        issue_comments.append(safe)
        redactions += count
    for item in review_raw:
        safe, count = _safe_comment(item)
        review_comments.append(safe)
        redactions += count

    return GitHubFetchResult(
        repository=repository,
        pr_number=pr_number,
        pull_request=pull_request,
        issue_comments=issue_comments,
        review_comments=review_comments,
        request_evidence=request_evidence,
        token_scope_assessment=token_assessment,
        secret_redactions=redactions,
    )
