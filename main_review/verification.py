"""THETECHGUY verification standard for Main Review.

This module checks whether a repository has enough proof to be considered
engineering-verified, not only CI-verified.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from .scanner import scan_repository

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


def _has_any_ci(root: Path) -> bool:
    workflows = root / ".github" / "workflows"
    return workflows.exists() and any(path.suffix.lower() in {".yml", ".yaml"} for path in workflows.iterdir())


def _has_manifest(root: Path) -> bool:
    manifests = {
        "pyproject.toml",
        "package.json",
        "requirements.txt",
        "go.mod",
        "cargo.toml",
        "pom.xml",
        "build.gradle",
        "settings.gradle",
        "pubspec.yaml",
        "composer.json",
        "Gemfile",
        "Package.swift",
        "CMakeLists.txt",
        "Makefile",
        "mix.exs",
        "build.sbt",
    }
    project_manifest_globs = ("*.csproj", "*.fsproj", "*.vbproj", "*.sln")
    return any((root / manifest).exists() for manifest in manifests) or any(
        any(root.glob(pattern)) for pattern in project_manifest_globs
    )


def _has_project_docs(root: Path) -> bool:
    return any((root / name).exists() for name in ["README.md", "README.mdx", "docs", "documentation"])


def _self_check_checks(root_path: Path) -> list[VerificationCheck]:
    return [
        VerificationCheck(
            name="project_scaffold",
            passed=_exists(root_path, "pyproject.toml") and _exists(root_path, "main_review"),
            evidence="pyproject.toml and main_review package must exist for Sentinel Review self-verification.",
        ),
        VerificationCheck(
            name="ci_workflow",
            passed=_exists(root_path, ".github", "workflows", "ci.yml"),
            evidence="Sentinel Review CI workflow must exist.",
        ),
        VerificationCheck(
            name="tests_present",
            passed=bool(scan_repository(root_path).tests),
            evidence="Test files must be detected.",
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


def _generic_checks(root_path: Path) -> list[VerificationCheck]:
    insight = scan_repository(root_path)
    return [
        VerificationCheck(
            name="project_manifest",
            passed=_has_manifest(root_path) or bool(insight.manifests),
            evidence="Repository should expose a recognized project manifest.",
        ),
        VerificationCheck(
            name="ci_workflow",
            passed=_has_any_ci(root_path),
            evidence="Repository should include at least one CI workflow file.",
        ),
        VerificationCheck(
            name="tests_present",
            passed=bool(insight.tests),
            evidence="Repository should contain detectable tests across supported languages.",
        ),
        VerificationCheck(
            name="project_documentation",
            passed=_has_project_docs(root_path),
            evidence="Repository should include README or docs.",
        ),
        VerificationCheck(
            name="source_present",
            passed=any(file.role in {"source", "ui", "database"} for file in insight.files),
            evidence="Repository should contain implementation source files.",
        ),
    ]


def verify_repository_standard(root: str | Path = ".", *, mode: Literal["auto", "self", "generic"] = "auto") -> VerificationReport:
    root_path = Path(root).resolve()
    if mode == "auto":
        mode = "self" if _exists(root_path, "main_review") and _exists(root_path, "docs", "19-thetechguy-engineering-standard.md") else "generic"
    checks = _self_check_checks(root_path) if mode == "self" else _generic_checks(root_path)

    required = [check for check in checks if check.required]
    required_passed = all(check.passed for check in required)
    optional_passed = all(check.passed for check in checks if not check.required)

    if required_passed and optional_passed:
        status: VerificationStatus = "verified"
        summary = f"Required and optional {mode} verification evidence is present."
        next_actions: list[str] = []
    elif required_passed:
        status = "partial"
        summary = f"Required {mode} verification evidence is present, but optional evidence is incomplete."
        next_actions = [check.evidence for check in checks if not check.required and not check.passed]
    else:
        status = "not_verified"
        summary = f"Required {mode} verification evidence is missing."
        next_actions = [check.evidence for check in required if not check.passed]

    return VerificationReport(
        status=status,
        checks=checks,
        summary=summary,
        next_actions=next_actions,
    )
