"""Review Memory for Main Review.

Review Memory stores engineering decisions, lessons, and principles as structured
JSON records. It is intentionally simple and file-based in v1 so it can work
locally, in CI, and inside any repository without a service dependency.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

MemoryKind = Literal["decision", "lesson", "principle", "boundary", "risk"]
MemoryStatus = Literal["proposed", "verified", "superseded", "rejected"]


@dataclass
class MemoryRecord:
    id: str
    kind: MemoryKind
    title: str
    summary: str
    reason: str
    status: MemoryStatus = "proposed"
    scope: str = "repository"
    evidence: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    applies_to: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    confidence: float = 0.5
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def normalized(self) -> "MemoryRecord":
        self.tags = sorted(set(self.tags))
        self.applies_to = sorted(set(self.applies_to))
        self.evidence = [item for item in self.evidence if item.strip()]
        self.supersedes = sorted(set(self.supersedes))
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return self


def default_memory_path(root: str | Path = ".") -> Path:
    return Path(root) / ".main-review" / "memory.json"


class ReviewMemoryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> list[MemoryRecord]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        records = payload.get("records", payload if isinstance(payload, list) else [])
        return [MemoryRecord(**record) for record in records]

    def save(self, records: list[MemoryRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "records": [asdict(record.normalized()) for record in records],
        }
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def add(self, record: MemoryRecord) -> MemoryRecord:
        records = self.load()
        if any(existing.id == record.id for existing in records):
            raise ValueError(f"Memory record already exists: {record.id}")
        record.normalized()
        records.append(record)
        self.save(records)
        return record

    def list(self, *, status: str | None = None, kind: str | None = None, tag: str | None = None) -> list[MemoryRecord]:
        records = self.load()
        if status:
            records = [record for record in records if record.status == status]
        if kind:
            records = [record for record in records if record.kind == kind]
        if tag:
            records = [record for record in records if tag in record.tags]
        return records

    def search(self, query: str) -> list[MemoryRecord]:
        needle = query.lower().strip()
        if not needle:
            return self.load()
        results: list[MemoryRecord] = []
        for record in self.load():
            haystack = "\n".join(
                [record.title, record.summary, record.reason, " ".join(record.tags), " ".join(record.applies_to)]
            ).lower()
            if needle in haystack:
                results.append(record)
        return results


def new_memory_record(
    *,
    kind: MemoryKind,
    title: str,
    summary: str,
    reason: str,
    status: MemoryStatus = "proposed",
    scope: str = "repository",
    evidence: list[str] | None = None,
    tags: list[str] | None = None,
    applies_to: list[str] | None = None,
    supersedes: list[str] | None = None,
    confidence: float = 0.5,
) -> MemoryRecord:
    return MemoryRecord(
        id=f"mem_{uuid4().hex[:12]}",
        kind=kind,
        title=title.strip(),
        summary=summary.strip(),
        reason=reason.strip(),
        status=status,
        scope=scope.strip() or "repository",
        evidence=evidence or [],
        tags=tags or [],
        applies_to=applies_to or [],
        supersedes=supersedes or [],
        confidence=confidence,
    ).normalized()
