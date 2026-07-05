"""Verification flow for Review Memory records.

This module promotes memory only when a reviewer or owner explicitly approves it.
The default learning state remains proposed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .memory import ReviewMemoryRecord, ReviewMemoryStore, default_memory_path


VALID_STATUSES = {"proposed", "verified", "superseded", "rejected"}


def _record_to_dict(record: ReviewMemoryRecord) -> dict[str, Any]:
    return record.__dict__.copy()


def set_memory_status(
    record_id: str,
    status: str,
    *,
    root: str | Path = ".",
    reason: str = "",
) -> dict[str, Any]:
    """Update one memory record status by id."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Unsupported memory status: {status}")
    store = ReviewMemoryStore(default_memory_path(root))
    records = store.load()
    updated: list[ReviewMemoryRecord] = []
    changed: ReviewMemoryRecord | None = None
    for record in records:
        if record.id == record_id:
            new_reason = record.reason
            if reason:
                new_reason = f"{record.reason}\n\nVerification note: {reason}".strip()
            changed = ReviewMemoryRecord(
                id=record.id,
                kind=record.kind,
                title=record.title,
                summary=record.summary,
                reason=new_reason,
                status=status,  # type: ignore[arg-type]
                scope=record.scope,
                evidence=record.evidence,
                tags=record.tags,
                applies_to=record.applies_to,
                confidence=record.confidence,
            )
            updated.append(changed)
        else:
            updated.append(record)
    if changed is None:
        raise KeyError(f"Memory record not found: {record_id}")
    store.save(updated)
    return {"updated": _record_to_dict(changed), "memory_path": str(default_memory_path(root))}


def list_memory_by_status(*, root: str | Path = ".", status: str = "proposed") -> dict[str, Any]:
    store = ReviewMemoryStore(default_memory_path(root))
    records = store.list(status=status)
    return {"status": status, "count": len(records), "records": [_record_to_dict(record) for record in records]}
