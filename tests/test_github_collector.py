from __future__ import annotations

import json
from pathlib import Path

from main_review.github_collector import (
    collect_github_comments,
    collect_github_comments_file,
    detect_reviewer_source,
)


def test_detect_reviewer_source() -> None:
    assert detect_reviewer_source("coderabbitai", "nit") == "coderabbit"
    assert detect_reviewer_source("github-actions[bot]", "done") == "github-actions"
    assert detect_reviewer_source("bot", "PR-Agent suggestion") == "qodo"
    assert detect_reviewer_source("reviewdog", "lint") == "reviewdog"
    assert detect_reviewer_source("jay", "manual note") == "github"


def test_collect_github_comments_normalizes_inline_and_issue_comments() -> None:
    payload = {
        "comments": [
            {
                "body": "Missing test for receiver validation.",
                "user": {"login": "coderabbitai"},
                "path": "src/api.py",
                "line": 42,
                "html_url": "https://example.test/comment/1",
                "type": "review_comment",
            },
            {
                "body": "Manual owner note.",
                "author": "jay",
            },
            {
                "body": "",
                "user": {"login": "empty"},
            },
        ]
    }

    comments = collect_github_comments(payload, repository="jaydumisuni/demo", pr_number=9)

    assert len(comments) == 2
    assert comments[0].source == "coderabbit"
    assert comments[0].repository == "jaydumisuni/demo"
    assert comments[0].pr_number == 9
    assert comments[0].path == "src/api.py"
    assert comments[0].line == 42
    assert comments[0].classification == "unclassified"
    assert "inline" in (comments[0].tags or [])
    assert comments[1].source == "github"


def test_collect_github_comments_file_outputs_ingestion_shape(tmp_path: Path) -> None:
    path = tmp_path / "github-comments.json"
    path.write_text(
        json.dumps(
            [
                {
                    "body": "CodeRabbit says this needs a regression test.",
                    "user": {"login": "coderabbitai"},
                    "filename": "tests/test_app.py",
                    "position": 7,
                }
            ]
        ),
        encoding="utf-8",
    )

    payload = collect_github_comments_file(path, repository="jaydumisuni/demo", pr_number=12)

    assert payload["summary"]["total"] == 1
    assert payload["summary"]["sources"] == ["coderabbit"]
    assert payload["summary"]["inline"] == 1
    assert payload["comments"][0]["source"] == "coderabbit"
    assert payload["comments"][0]["classification"] == "unclassified"
    assert payload["comments"][0]["path"] == "tests/test_app.py"


def test_collect_github_comments_respects_explicit_generic_source() -> None:
    comments = collect_github_comments(
        {
            "comments": [
                {
                    "source": "reference-reviewer",
                    "body": "Generic reviewer evidence.",
                    "user": {"login": "bot"},
                }
            ]
        }
    )

    assert comments[0].source == "reference-reviewer"
