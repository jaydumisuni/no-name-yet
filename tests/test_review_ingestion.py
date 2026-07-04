from __future__ import annotations

import json
from pathlib import Path

from main_review.review_ingestion import (
    export_learning_candidates,
    ingest_external_review_file,
    load_external_comments,
    normalize_classification,
    summarize_comments,
)


def test_normalize_classification_accepts_symbols_and_words() -> None:
    assert normalize_classification("🟢") == "correct"
    assert normalize_classification("green") == "correct"
    assert normalize_classification("🟡") == "suggestion"
    assert normalize_classification("🔴") == "reject"
    assert normalize_classification("🧠") == "save_pattern"
    assert normalize_classification("unknown") == "unclassified"


def test_ingest_external_review_file_summarizes_and_exports_learning(tmp_path: Path) -> None:
    payload = {
        "comments": [
            {
                "source": "coderabbit",
                "body": "Missing receiver validation test.",
                "repository": "jaydumisuni/demo",
                "pr_number": 7,
                "path": "src/api.py",
                "line": 42,
                "classification": "🟢",
                "reason": "This is a real contract gap.",
                "tags": ["testing", "contract"],
                "url": "https://example.test/comment/1",
            },
            {
                "source": "coderabbit",
                "body": "Consider renaming this variable.",
                "classification": "🟡",
            },
            {
                "source": "coderabbit",
                "body": "Use a different style that conflicts with project conventions.",
                "classification": "🔴",
            },
            {
                "source": "coderabbit",
                "body": "Repeated config-risk pattern.",
                "classification": "🧠",
                "tags": ["config-risk"],
            },
        ]
    }
    path = tmp_path / "comments.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = ingest_external_review_file(path)

    assert result["summary"] == {
        "total": 4,
        "correct": 1,
        "suggestion": 1,
        "reject": 1,
        "save_pattern": 1,
        "unclassified": 0,
    }
    assert len(result["learning_candidates"]) == 2
    assert result["learning_candidates"][0]["tags"] == ["coderabbit", "contract", "external-review", "testing"]


def test_load_list_payload_and_summarize(tmp_path: Path) -> None:
    path = tmp_path / "comments.json"
    path.write_text(json.dumps([{"source": "qodo", "body": "Save this", "classification": "save"}]), encoding="utf-8")

    comments = load_external_comments(path)
    summary = summarize_comments(comments)
    candidates = export_learning_candidates(comments)

    assert summary.save_pattern == 1
    assert candidates[0]["kind"] == "principle"
    assert candidates[0]["tags"] == ["external-review", "qodo"]
