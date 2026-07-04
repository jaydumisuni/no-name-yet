"""GitHub PR comment collector foundation.

This module normalizes GitHub pull request discussion/comment payloads into the
same JSON shape accepted by the external review ingestion pipeline.

It intentionally has no network dependency. The GitHub connector or future app
bridge can fetch comments, then pass the raw JSON into this collector.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GitHubCollectedComment:
    source: str
    body: str
    repository: str = ""
    pr_number: int | None = None
    path: str | None = None
    line: int | None = None
    author: str | None = None
    url: str | None = None
    classification: str = "unclassified"
    reason: str = ""
    tags: list[str] | None = None
    raw_type: str = "github-comment"

    def to_ingestion_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("raw_type", None)
        payload["tags"] = self.tags or []
        return payload


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("comments", "items", "timeline", "review_comments", "discussion"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    return []


def detect_reviewer_source(author: str | None, body: str = "") -> str:
    text = f"{author or ''}\n{body}".lower()
    if "coderabbit" in text or "code rabbit" in text:
        return "coderabbit"
    if "qodo" in text or "pr-agent" in text or "pr agent" in text:
        return "qodo"
    if "reviewdog" in text:
        return "reviewdog"
    if "github-actions" in text or "github actions" in text:
        return "github-actions"
    return "github"


def collect_github_comments(
    payload: Any,
    *,
    repository: str = "",
    pr_number: int | None = None,
) -> list[GitHubCollectedComment]:
    comments: list[GitHubCollectedComment] = []
    for item in _extract_items(payload):
        body = str(item.get("body") or item.get("review") or item.get("comment") or "").strip()
        if not body:
            continue

        user = item.get("user") or item.get("author") or {}
        if isinstance(user, dict):
            author = _optional_str(user.get("login") or user.get("name"))
        else:
            author = _optional_str(user)

        path = _optional_str(item.get("path") or item.get("file") or item.get("filename"))
        line = _optional_int(item.get("line") or item.get("original_line") or item.get("position"))
        url = _optional_str(item.get("html_url") or item.get("url") or item.get("display_url"))
        source = detect_reviewer_source(author, body)
        tags = ["github-pr-comment", source]
        if path:
            tags.append("inline")

        comments.append(
            GitHubCollectedComment(
                source=source,
                body=body,
                repository=str(item.get("repository") or repository),
                pr_number=_optional_int(item.get("pr_number")) or pr_number,
                path=path,
                line=line,
                author=author,
                url=url,
                tags=tags,
                raw_type=str(item.get("type") or item.get("event") or "github-comment"),
            )
        )
    return comments


def collect_github_comments_file(
    path: str | Path,
    *,
    repository: str = "",
    pr_number: int | None = None,
) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    comments = collect_github_comments(payload, repository=repository, pr_number=pr_number)
    return {
        "comments": [comment.to_ingestion_dict() for comment in comments],
        "summary": {
            "total": len(comments),
            "sources": sorted({comment.source for comment in comments}),
            "inline": sum(1 for comment in comments if comment.path),
        },
    }
