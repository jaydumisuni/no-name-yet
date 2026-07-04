"""THETECHGUY verification standard for Main Review.

This module checks whether a repository has enough proof to be considered
engineering-verified, not only CI-verified.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

VerificationStatus = Literal["verified", "partial", "not_verified"]


@dataclass(frozen=True)
class VerificationCheck:
    name: str
    passed: bool
    evidence: str
    required: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class VerificationReport:
    status: VerificationStatus
    checks: list[VerificationCheck] = field(default_factory=list)
    summary: str = ""
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "summary": self.summary,
            "checks": [check.to_dict() for check in self.checks],
            "next_actions": self.next_actions,
        }


def _exists(root: Path, *parts: str) -> bool:
    return (root.joinpath(*parts)).exists()


def verify_repository_standard(root: str | Path = ".") -> VerificationReport:
    root_path = Path(root).resolve()
    checks = [
        VerificationCheck(
            name="project_scaffold",
            passed=_exists(root_path, "pyproject.toml") and _exists(root_path, "main_review"),
            evidence="pyproject.toml and main_review package must exist.",
        ),
        VerificationCheck(
            name="ci_workflow",
            passed=_exists(root_path, ".github", "workflows", "ci.yml"),
            evidence="GitHub Actions CI workflow must exist.",
        ),
        VerificationCheck(
            name="tests_present",
            passed=_exists(root_path, "tests"),
            evidence="tests/ directory must exist.",
        ),
        VerificationCheck(
            name="engineering_standard_documented",
            passed=_exists(root_path, "docs", "19-thetechguy-engineering-standard.md"),
            evidence="THETECHGUY Engineering Standard document must exist.",
        ),
        VerificationCheck(
            name="clean_clone_workflow_documented",
            passed=_exists(root_path, "docs", "20-clean-clone-proof.md"),
            evidence="Clean clone proof workflow must be documented.",
        ),
        VerificationCheck(
            name="external_review_learning_documented",
            passed=_exists(root_path, "docs", "12-external-review-learning-loop.md"),
            evidence="External review learning loop must be documented.",
        ),
        VerificationCheck(
            name="open_source_reviewer_notes_documented",
            passed=_exists(root_path, "docs", "21-open-source-reviewer-patterns.md"),
            evidence="Open-source reviewer pattern notes must be documented.",
            required=False,
        ),
    ]

    required = [check for check in checks if check.required]
    required_passed = all(check.passed for check in required)
    optional_passed = all(check.passed for check in checks if not check.required)

    if required_passed and optional_passed:
        status: VerificationStatus = "verified"
        summary = "Required and optional verification evidence is present."
        next_actions: list[str] = []
    elif required_passed:
        status = "partial"
        summary = "Required verification evidence is present, but optional reviewer-learning evidence is incomplete."
        next_actions = [
            "Complete optional reviewer pattern documentation.",
            "Run clean-clone proof and record the result.",
        ]
    else:
        status = "not_verified"
        summary = "Required verification evidence is missing."
        next_actions = [check.evidence for check in required if not check.passed]

    return VerificationReport(
        status=status,
        checks=checks,
        summary=summary,
        next_actions=next_actions,
    )
