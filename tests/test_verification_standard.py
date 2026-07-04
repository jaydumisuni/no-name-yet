from __future__ import annotations

from pathlib import Path

from main_review.verification import verify_repository_standard


def test_verification_reports_missing_required_evidence(tmp_path: Path) -> None:
    report = verify_repository_standard(tmp_path)

    assert report.status == "not_verified"
    assert report.next_actions


def test_verification_reports_verified_when_required_and_optional_evidence_exists(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "main_review").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    for name in [
        "12-external-review-learning-loop.md",
        "19-thetechguy-engineering-standard.md",
        "20-clean-clone-proof.md",
        "21-open-source-reviewer-patterns.md",
    ]:
        (tmp_path / "docs" / name).write_text("# Doc\n", encoding="utf-8")

    report = verify_repository_standard(tmp_path)

    assert report.status == "verified"
    assert not report.next_actions


def test_verification_reports_partial_when_optional_evidence_missing(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "main_review").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    for name in [
        "12-external-review-learning-loop.md",
        "19-thetechguy-engineering-standard.md",
        "20-clean-clone-proof.md",
    ]:
        (tmp_path / "docs" / name).write_text("# Doc\n", encoding="utf-8")

    report = verify_repository_standard(tmp_path)

    assert report.status == "partial"
    assert report.next_actions
