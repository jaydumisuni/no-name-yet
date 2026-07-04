from __future__ import annotations

from pathlib import Path

from main_review.proof_suite import assert_end_to_end_proof, run_end_to_end_proof


def _make_verified_repo(root: Path) -> None:
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (root / "main_review").mkdir()
    (root / "tests").mkdir()
    (root / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (root / "docs").mkdir()
    for name in [
        "12-external-review-learning-loop.md",
        "19-thetechguy-engineering-standard.md",
        "20-clean-clone-proof.md",
        "21-open-source-reviewer-patterns.md",
    ]:
        (root / "docs" / name).write_text("# Doc\n", encoding="utf-8")


def test_end_to_end_proof_passes_all_phases(tmp_path: Path) -> None:
    _make_verified_repo(tmp_path)

    result = run_end_to_end_proof(tmp_path)

    assert result["passed"] is True
    assert all(result["phases"].values())
    assert result["review_batch_summary"]["collected_comments"] == 3
    assert result["review_batch_summary"]["memory_written"] == 2


def test_end_to_end_proof_exits_on_failure(tmp_path: Path) -> None:
    try:
        assert_end_to_end_proof(tmp_path)
    except SystemExit as exc:
        assert "End-to-end proof failed" in str(exc)
    else:
        raise AssertionError("proof suite should fail for an empty repository")
