from __future__ import annotations

import json
from pathlib import Path

from main_review.memory import ReviewMemoryStore, default_memory_path
from main_review.memory_ingestion import write_learning_candidates_to_memory


def test_write_learning_candidates_to_memory(tmp_path: Path) -> None:
    review_file = tmp_path / "comments.json"
    review_file.write_text(
        json.dumps(
            {
                "comments": [
                    {
                        "source": "coderabbit",
                        "body": "Missing receiver validation test.",
                        "classification": "🟢",
                        "reason": "Real contract gap.",
                        "tags": ["testing", "contract"],
                        "path": "src/api.py",
                    },
                    {
                        "source": "coderabbit",
                        "body": "Stylistic preference only.",
                        "classification": "🔴",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    result = write_learning_candidates_to_memory(review_file, root=tmp_path)
    store = ReviewMemoryStore(default_memory_path(tmp_path))
    records = store.load()

    assert result["written_count"] == 1
    assert len(records) == 1
    assert records[0].kind == "lesson"
    assert records[0].status == "proposed"
    assert records[0].tags == ["coderabbit", "contract", "external-review", "testing"]
    assert records[0].applies_to == ["src/api.py"]


def test_write_learning_candidates_can_filter_by_tag(tmp_path: Path) -> None:
    review_file = tmp_path / "comments.json"
    review_file.write_text(
        json.dumps(
            [
                {
                    "source": "qodo",
                    "body": "Security pattern.",
                    "classification": "🧠",
                    "tags": ["security"],
                },
                {
                    "source": "qodo",
                    "body": "Docs pattern.",
                    "classification": "🧠",
                    "tags": ["documentation"],
                },
            ]
        ),
        encoding="utf-8",
    )

    result = write_learning_candidates_to_memory(review_file, root=tmp_path, only_tags=["security"])
    records = ReviewMemoryStore(default_memory_path(tmp_path)).load()

    assert result["written_count"] == 1
    assert result["skipped_count"] == 1
    assert records[0].kind == "principle"
    assert "security" in records[0].tags
