"""Diff review mode for Main Review.

Patch 05 adds local diff awareness without GitHub API dependency. It inspects a
changed-file list and classifies the review impact before handing findings to
the deterministic verdict engine.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from .evidence import EvidenceFinding
from .languages import classify_role, detect_language, is_high_risk_path
from .verdict import decide_verdict


@dataclass(frozen=True)
class ChangedFileInsight:
    path: str
    language: str
    role: str
    high_risk: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DiffReviewInput:
    changed_files: list[str] = field(default_factory=list)


def parse_changed_files_text(text: str) -> list[str]:
    """Parse newline, comma, or JSON-ish changed-file input safely.

    This intentionally accepts simple text because early local mode should work
    with `git diff --name-only` output and copied PR file lists.
    """
    normalized = text.replace(",", "\n").replace("[", "\n").replace("]", "\n").replace('"', "")
    return [line.strip() for line in normalized.splitlines() if line.strip()]


def classify_changed_files(changed_files: list[str]) -> list[ChangedFileInsight]:
    return [
        ChangedFileInsight(
            path=path,
            language=detect_language(path),
            role=classify_role(path),
            high_risk=is_high_risk_path(path),
        )
        for path in sorted(set(changed_files))
    ]


def diff_findings(changed_files: list[str]) -> list[EvidenceFinding]:
    insights = classify_changed_files(changed_files)
    findings: list[EvidenceFinding] = []

    if not insights:
        findings.append(
            EvidenceFinding(
                provider="diff-review",
                severity="major",
                category="repository",
                message="No changed files were provided for diff review.",
                evidence="Diff review requires a changed-file list.",
                confidence=0.8,
            )
        )
        return findings

    risky = [item for item in insights if item.high_risk]
    tests = [item for item in insights if item.role == "test"]
    source = [item for item in insights if item.role == "source"]
    docs = [item for item in insights if item.role == "documentation"]

    for item in risky:
        findings.append(
            EvidenceFinding(
                provider="diff-review",
                severity="major",
                category="risk",
                path=item.path,
                message="Changed file is in a high-risk path.",
                evidence="CI, infrastructure, scripts, deployment, or sensitive paths need deeper review.",
                confidence=0.85,
            )
        )

    if source and not tests:
        findings.append(
            EvidenceFinding(
                provider="diff-review",
                severity="major",
                category="testing",
                message="Source files changed without changed tests.",
                evidence=f"Detected {len(source)} source change(s) and 0 test change(s).",
                confidence=0.75,
            )
        )

    if docs and not source and not risky:
        findings.append(
            EvidenceFinding(
                provider="diff-review",
                severity="note",
                category="documentation",
                message="Documentation-only change detected.",
                evidence="Docs-only changes normally require lighter review unless public promises or architecture docs changed.",
                confidence=0.7,
            )
        )

    return findings


def review_changed_files(changed_files: list[str]) -> dict[str, object]:
    insights = classify_changed_files(changed_files)
    findings = diff_findings(changed_files)
    evidence_payload = {
        "mode": "diff",
        "changed_files": [item.to_dict() for item in insights],
        "findings": [finding.to_dict() for finding in findings],
        "finding_count": len(findings),
    }
    return {
        "verdict": decide_verdict(evidence_payload).to_dict(),
        "evidence": evidence_payload,
    }


def review_changed_files_file(path: str | Path) -> dict[str, object]:
    changed_files = parse_changed_files_text(Path(path).read_text(encoding="utf-8"))
    return review_changed_files(changed_files)
