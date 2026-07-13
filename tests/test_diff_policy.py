from __future__ import annotations

from pathlib import Path

from main_review.diff_policy import normalize_diff_review
from main_review.diff_review import review_changed_files


def test_high_risk_path_remains_major_without_assurance(tmp_path: Path) -> None:
    changed = [".github/workflows/main-review.yml"]

    normalized = normalize_diff_review(review_changed_files(changed), tmp_path, changed)

    assert normalized["verdict"]["verdict"] == "NEEDS WORK"
    assert normalized["policy_adjustments"] == []


def test_complete_assurance_document_turns_path_risk_into_review_note(tmp_path: Path) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "main-review.yml").write_text("name: review\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    assurance = tmp_path / "docs" / "main-review-assurance.md"
    assurance.write_text(
        "# Assurance\n\n"
        "Target: `.github/workflows/main-review.yml`\n\n"
        "## Purpose\nGate the actual JSON verdict.\n\n"
        "## Permissions\nRead-only contents.\n\n"
        "## Secrets\nOne optional environment secret.\n\n"
        "## Rollback\nRevert the workflow.\n\n"
        "## Proof\nTests and reviewer artifact.\n",
        encoding="utf-8",
    )
    changed = [".github/workflows/main-review.yml", "docs/main-review-assurance.md"]

    normalized = normalize_diff_review(review_changed_files(changed), tmp_path, changed)

    assert normalized["verdict"]["verdict"] == "PASS"
    finding = normalized["evidence"]["findings"][0]
    assert finding["severity"] == "note"
    assert finding["assurance_document"] == "docs/main-review-assurance.md"
    assert normalized["policy_adjustments"][0]["path"] == ".github/workflows/main-review.yml"


def test_incomplete_assurance_does_not_clear_high_risk_change(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "partial.md").write_text(
        "Target: `.github/workflows/main-review.yml`\nPurpose: change review.\nProof: tests.\n",
        encoding="utf-8",
    )
    changed = [".github/workflows/main-review.yml", "docs/partial.md"]

    normalized = normalize_diff_review(review_changed_files(changed), tmp_path, changed)

    assert normalized["verdict"]["verdict"] == "NEEDS WORK"
    assert normalized["policy_adjustments"] == []
