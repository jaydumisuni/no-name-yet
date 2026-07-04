"""Evidence providers for Main Review.

Evidence providers produce facts. They do not decide the final verdict.
Patch 03 keeps providers static and safe: no project code execution.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Protocol

from .models import RepositoryInsight
from .scanner import scan_repository

Severity = Literal["blocker", "major", "minor", "note"]
Category = Literal["security", "testing", "documentation", "architecture", "repository", "risk"]


@dataclass(frozen=True)
class EvidenceFinding:
    provider: str
    severity: Severity
    category: Category
    message: str
    path: str | None = None
    line: int | None = None
    evidence: str = ""
    confidence: float = 0.5

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class EvidenceProvider(Protocol):
    name: str

    def collect(self, root: Path, insight: RepositoryInsight) -> list[EvidenceFinding]:
        ...


SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private key", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("generic api key assignment", re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{12,}['\"]")),
    ("github token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}")),
    ("aws access key", re.compile(r"AKIA[0-9A-Z]{16}")),
)

TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".c", ".h", ".cpp", ".hpp",
    ".cs", ".php", ".rb", ".swift", ".dart", ".lua", ".r", ".R", ".md", ".mdx", ".txt", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".sh", ".ps1", ".sql", ".html", ".css",
}


class SecretEvidenceProvider:
    name = "secret-scanner"

    def collect(self, root: Path, insight: RepositoryInsight) -> list[EvidenceFinding]:
        findings: list[EvidenceFinding] = []
        for file in insight.files:
            path = root / file.path
            if path.suffix not in TEXT_EXTENSIONS and path.name not in {"Dockerfile", "Containerfile"}:
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for number, line in enumerate(lines, start=1):
                for label, pattern in SECRET_PATTERNS:
                    if pattern.search(line):
                        findings.append(
                            EvidenceFinding(
                                provider=self.name,
                                severity="blocker",
                                category="security",
                                path=file.path,
                                line=number,
                                message=f"Possible {label} detected.",
                                evidence="Sensitive-looking value matched a secret pattern.",
                                confidence=0.9,
                            )
                        )
        return findings


class TestCoverageEvidenceProvider:
    name = "test-coverage-checker"

    def collect(self, root: Path, insight: RepositoryInsight) -> list[EvidenceFinding]:
        source_count = sum(1 for file in insight.files if file.role == "source")
        test_count = len(insight.tests)
        if source_count and not test_count:
            return [
                EvidenceFinding(
                    provider=self.name,
                    severity="major",
                    category="testing",
                    message="Source files exist but no tests were detected.",
                    evidence=f"Detected {source_count} source file(s) and 0 test files.",
                    confidence=0.85,
                )
            ]
        if test_count < max(1, source_count // 5) and source_count >= 10:
            return [
                EvidenceFinding(
                    provider=self.name,
                    severity="minor",
                    category="testing",
                    message="Test footprint appears low compared with source footprint.",
                    evidence=f"Detected {source_count} source file(s) and {test_count} test file(s).",
                    confidence=0.65,
                )
            ]
        return []


class DocumentationEvidenceProvider:
    name = "documentation-checker"

    def collect(self, root: Path, insight: RepositoryInsight) -> list[EvidenceFinding]:
        if not insight.docs:
            return [
                EvidenceFinding(
                    provider=self.name,
                    severity="major",
                    category="documentation",
                    message="No documentation files were detected.",
                    evidence="README/docs are absent from the repository scan.",
                    confidence=0.8,
                )
            ]
        if "README.md" not in insight.docs and "readme.md" not in {doc.lower() for doc in insight.docs}:
            return [
                EvidenceFinding(
                    provider=self.name,
                    severity="minor",
                    category="documentation",
                    message="Documentation exists but no top-level README.md was detected.",
                    evidence=f"Detected docs: {', '.join(insight.docs[:5])}.",
                    confidence=0.7,
                )
            ]
        return []


class RiskPathEvidenceProvider:
    name = "risk-path-checker"

    def collect(self, root: Path, insight: RepositoryInsight) -> list[EvidenceFinding]:
        return [
            EvidenceFinding(
                provider=self.name,
                severity="note",
                category="risk",
                path=path,
                message="High-risk path detected for review attention.",
                evidence="Infrastructure, CI, deployment, or sensitive path classification.",
                confidence=0.75,
            )
            for path in insight.high_risk_files
        ]


DEFAULT_PROVIDERS: tuple[EvidenceProvider, ...] = (
    SecretEvidenceProvider(),
    TestCoverageEvidenceProvider(),
    DocumentationEvidenceProvider(),
    RiskPathEvidenceProvider(),
)


def collect_evidence(root: str | Path, providers: tuple[EvidenceProvider, ...] = DEFAULT_PROVIDERS) -> dict[str, object]:
    root_path = Path(root).resolve()
    insight = scan_repository(root_path)
    findings: list[EvidenceFinding] = []
    for provider in providers:
        findings.extend(provider.collect(root_path, insight))
    return {
        "root": str(root_path),
        "repository": insight.to_dict(),
        "findings": [finding.to_dict() for finding in findings],
        "finding_count": len(findings),
    }
