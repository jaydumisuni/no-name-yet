from __future__ import annotations

import json
from pathlib import Path

from main_review.pr_reviewer import _decide, render_pr_review_markdown, run_independent_pr_review


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
    assert packet["cpl_review"]["status"] == "disabled"
    assert packet["semantic_review"] == packet["cpl_review"]
    assert "External reviewer comments are optional" in rendered
    assert "Cpl status: disabled" in rendered
    assert "Cpl role: Corporal Specialist" in rendered
    assert packet["officer_council"]["model_required"] is False


def test_not_deployed_cpl_does_not_claim_unresolved_council_gaps() -> None:
    verdict = _decide(
        {"verdict": "PASS"},
        {"passed": True, "blockers": []},
        {"verdict": {"verdict": "PASS"}},
        {"verdict": "PASS", "ranked_findings": []},
        {"confidence_after_challenge": 0.9},
        {
            "status": "error",
            "policy": "preferred",
            "verdict": "PASS",
            "confidence": 0.0,
            "findings": [],
            "council": {"mode": "not_deployed", "complete": False},
        },
        {"consensus": "PASS"},
    )

    assert verdict.verdict == "APPROVE"
    assert any("model amplification was unavailable" in note for note in verdict.notes)
    assert not any("unresolved council gaps" in note for note in verdict.notes)


def test_deployed_incomplete_cpl_preserves_unresolved_gap_note() -> None:
    verdict = _decide(
        {"verdict": "PASS"},
        {"passed": True, "blockers": []},
        {"verdict": {"verdict": "PASS"}},
        {"verdict": "PASS", "ranked_findings": []},
        {"confidence_after_challenge": 0.9},
        {
            "status": "completed",
            "policy": "preferred",
            "verdict": "NEEDS WORK",
            "confidence": 0.7,
            "findings": [],
            "council": {"mode": "elastic_multi_model", "complete": False},
        },
        {"consensus": "NEEDS WORK"},
    )

    assert verdict.verdict == "COMMENT"
    assert any("unresolved council gaps" in note for note in verdict.notes)


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
