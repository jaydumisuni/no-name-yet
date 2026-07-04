"""Data models for repository intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FileInsight:
    path: str
    language: str
    role: str
    high_risk: bool = False


@dataclass
class RepositoryInsight:
    root: str
    files: list[FileInsight] = field(default_factory=list)
    languages: dict[str, int] = field(default_factory=dict)
    roles: dict[str, int] = field(default_factory=dict)
    high_risk_files: list[str] = field(default_factory=list)
    docs: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)
    manifests: list[str] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return len(self.files)

    def to_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "total_files": self.total_files,
            "languages": dict(sorted(self.languages.items())),
            "roles": dict(sorted(self.roles.items())),
            "high_risk_files": sorted(self.high_risk_files),
            "docs": sorted(self.docs),
            "tests": sorted(self.tests),
            "manifests": sorted(self.manifests),
            "files": [file.__dict__ for file in self.files],
        }
