"""Batch workflow for external review learning.

Patch 09 provides a single local pipeline that can process exported GitHub PR
comments, normalize them, ingest classifications, and optionally write accepted
learning candidates into Review Memory.
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .github_collector import collect_github_comments_file
from .memory_ingestion import write_learning_candidates_to_memory
from .review_ingestion import ingest_external_review_file


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_review_learning_batch(
    comments_file: str | Path,
    *,
    root: str | Path = ".",
    repository: str = "",
    pr_number: int | None = None,
    write_memory: bool = False,
    status: str = "proposed",
    only_tags: list[str] | None = None,
) -> dict[str, Any]:
    """Run the comment collection -> ingestion -> optional memory write pipeline."""
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        normalized_path = temp_path / "normalized-comments.json"
        normalized = collect_github_comments_file(
            comments_file,
            repository=repository,
            pr_number=pr_number,
        )
        _write_json(normalized_path, normalized)

        ingestion = ingest_external_review_file(normalized_path)
        result: dict[str, Any] = {
            "normalized": normalized,
            "ingestion": ingestion,
            "memory": None,
        }

        if write_memory:
            result["memory"] = write_learning_candidates_to_memory(
                normalized_path,
                root=root,
                status=status,
                only_tags=only_tags or [],
            )

        return result


def batch_summary(batch_result: dict[str, Any]) -> dict[str, object]:
    normalized = batch_result.get("normalized", {}) if isinstance(batch_result, dict) else {}
    ingestion = batch_result.get("ingestion", {}) if isinstance(batch_result, dict) else {}
    memory = batch_result.get("memory") if isinstance(batch_result, dict) else None

    normalized_summary = normalized.get("summary", {}) if isinstance(normalized, dict) else {}
    ingestion_summary = ingestion.get("summary", {}) if isinstance(ingestion, dict) else {}

    return {
        "collected_comments": normalized_summary.get("total", 0),
        "sources": normalized_summary.get("sources", []),
        "inline_comments": normalized_summary.get("inline", 0),
        "classification_summary": ingestion_summary,
        "learning_candidates": len(ingestion.get("learning_candidates", [])) if isinstance(ingestion, dict) else 0,
        "memory_written": memory.get("written_count", 0) if isinstance(memory, dict) else 0,
    }
