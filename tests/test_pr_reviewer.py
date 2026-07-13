from __future__ import annotations

import json
from pathlib import Path

from main_review.pr_reviewer import render_pr_review_markdown, run_independent_pr_review


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


def test_independent_pr_review_approves_verified_repo_without_external_reviewer(tmp_path: Path) -> None:
    _make_verified_repo(tmp_path)

    packet = run_independent_pr_review(tmp_path, changed_files=["src/app.py", "tests/test_app.py"])
    rendered = render_pr_review_markdown(packet)

    assert packet["verdict"]["verdict"] == "APPROVE"
    assert packet["standard"]["passed"] is True
    assert packet["challenge"]["trusted"] is True
    assert packet["semantic_review"]["status"] == "disabled"
    assert "External reviewer comments are optional" in rendered
    assert "Semantic review status: disabled" in rendered


def test_independent_pr_review_requests_changes_when_tests_missing(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    packet = run_independent_pr_review(tmp_path, changed_files=["src/app.py"])

    assert packet["verdict"]["verdict"] == "REQUEST_CHANGES"
    assert packet["verdict"]["required_actions"]


def test_independent_pr_review_can_consume_external_learning_without_needing_it(tmp_path: Path) -> None:
    _make_verified_repo(tmp_path)
    comments = tmp_path / "comments.json"
    comments.write_text(
        json.dumps({"comments": [{"source": "coderabbit", "body": "real issue", "classification": "correct"}]}),
        encoding="utf-8",
    )

    packet = run_independent_pr_review(
        tmp_path,
        changed_files=["src/app.py", "tests/test_app.py"],
        external_review_file=comments,
    )

    assert packet["verdict"]["verdict"] == "APPROVE"
    assert packet["external_decisions"]["summary"]["fix"] == 1
