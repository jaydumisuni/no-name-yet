from __future__ import annotations

from pathlib import Path

from main_review.app_bridge import handle_app_review_request
from main_review.cli import main


def _make_repo(root: Path) -> None:
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / "main_review").mkdir()
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("def ok():\n    return True\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
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


def test_app_bridge_returns_ui_ready_payload(tmp_path: Path) -> None:
    _make_repo(tmp_path)

    payload = handle_app_review_request({"root": str(tmp_path), "mode": "pull_request", "changed_files": ["src/app.py", "tests/test_app.py"]})

    assert payload["ok"] is True
    assert payload["service"] == "Sergeant"
    assert payload["status"] in {"pass", "needs_work", "block"}
    assert "markdown" in payload
    assert "packet" in payload


def test_app_bridge_cli_runs(tmp_path: Path) -> None:
    _make_repo(tmp_path)

    exit_code = main(["app-review", str(tmp_path), "--mode", "pull_request", "--files", "src/app.py,tests/test_app.py"])

    assert exit_code == 0
