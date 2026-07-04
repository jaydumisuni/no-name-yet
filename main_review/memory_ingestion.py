"""Write accepted external review learning candidates into Review Memory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .memory import ReviewMemoryStore, default_memory_path, new_memory_record
from .review_ingestion import ingest_external_review_file


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def write_learning_candidates_to_memory(
    review_file: str | Path,
    *,
    root: str | Path = ".",
    status: str = "proposed",
    only_tags: list[str] | None = None,
) -> dict[str, object]:
    """Ingest an external review export and persist learning candidates.

    Candidates are intentionally written as proposed by default. A human/owner can
    later verify or reject them after scrutiny.
    """
    ingestion = ingest_external_review_file(review_file)
    candidates = ingestion.get("learning_candidates", [])
    store = ReviewMemoryStore(default_memory_path(root))
    written: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    required_tags = set(only_tags or [])

    if not isinstance(candidates, list):
        candidates = []

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        tags = _as_list(candidate.get("tags"))
        if required_tags and not required_tags.intersection(tags):
            skipped.append({"title": str(candidate.get("title", "")), "reason": "tag filter"})
            continue

        record = new_memory_record(
            kind=str(candidate.get("kind", "lesson")),  # type: ignore[arg-type]
            title=str(candidate.get("title", "External review learning")),
            summary=str(candidate.get("summary", "")),
            reason=str(candidate.get("reason", "External review learning candidate.")),
            status=status,  # type: ignore[arg-type]
            evidence=_as_list(candidate.get("evidence")),
            tags=tags,
            applies_to=_as_list(candidate.get("applies_to")),
            confidence=float(candidate.get("confidence", 0.5)),
        )
        saved = store.add(record)
        written.append(saved.__dict__)

    return {
        "summary": ingestion.get("summary", {}),
        "written_count": len(written),
        "skipped_count": len(skipped),
        "written": written,
        "skipped": skipped,
        "memory_path": str(default_memory_path(root)),
    }
