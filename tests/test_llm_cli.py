from __future__ import annotations

import json
from pathlib import Path

from main_review.cli import main


def _reviewable_repo(root: Path) -> None:
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (root / "main_review").mkdir()
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
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


def test_llm_status_reports_disabled_without_exposing_credentials(monkeypatch, capsys) -> None:
    monkeypatch.setenv("SERGEANT_LLM_ENABLED", "false")
    monkeypatch.setenv("SERGEANT_LLM_API_KEY", "do-not-print-this")

    assert main(["llm-status"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "disabled"
    assert payload["route"] is None
    assert "do-not-print-this" not in json.dumps(payload)
    assert payload["default_model_policy"][0] == "GLM-5.2"


def test_llm_status_require_fails_when_no_route_exists(monkeypatch, capsys) -> None:
    monkeypatch.setenv("SERGEANT_LLM_ENABLED", "true")
    monkeypatch.setenv("SERGEANT_LLM_PROVIDER", "fcc")
    monkeypatch.setenv("SERGEANT_LLM_TIMEOUT_SECONDS", "1")

    assert main(["llm-status", "--require"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "unavailable"


def test_pr_review_command_runs_full_reviewer_with_workspace_semantic_scope(tmp_path: Path, capsys) -> None:
    _reviewable_repo(tmp_path)

    assert main(["pr-review", str(tmp_path)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["verdict"]["verdict"] in {"APPROVE", "COMMENT", "REQUEST_CHANGES"}
    assert payload["semantic_review"]["status"] == "disabled"
    assert payload["semantic_review"]["policy"] == "preferred"
    assert payload["semantic_files"]
    assert "src/app.py" in payload["semantic_files"]
