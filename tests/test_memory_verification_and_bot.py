from __future__ import annotations

from pathlib import Path

from main_review.github_bot import build_github_review_payload
from main_review.memory import ReviewMemoryStore, default_memory_path, new_memory_record
from main_review.memory_verification import list_memory_by_status, set_memory_status


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


def test_memory_status_can_be_verified(tmp_path: Path) -> None:
    store = ReviewMemoryStore(default_memory_path(tmp_path))
    record = new_memory_record(
        kind="lesson",
        title="Receiver proof",
        summary="Receiver-side proof matters.",
        reason="Approved by owner.",
        tags=["review"],
    )
    store.add(record)

    result = set_memory_status(record.id, "verified", root=tmp_path, reason="Confirmed pattern.")
    listed = list_memory_by_status(root=tmp_path, status="verified")

    assert result["updated"]["status"] == "verified"
    assert listed["count"] == 1


def test_github_review_payload_is_independent(tmp_path: Path) -> None:
    _make_verified_repo(tmp_path)

    payload = build_github_review_payload(tmp_path, changed_files=["src/app.py", "tests/test_app.py"])

    assert payload["action"] == "APPROVE"
    assert "Main Review is the reviewer" in payload["body"]
    assert payload["packet"]["verdict"]["verdict"] == "APPROVE"
