from __future__ import annotations

import json
from pathlib import Path

import pytest

import main_review.app_bridge as app_bridge
from main_review.app_bridge import handle_app_review_request
from main_review.cli import main
from main_review.review_contract import CONTRACT_VERSION


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
    assert payload["schema_version"] == CONTRACT_VERSION
    assert payload["service"] == "Sergeant"
    assert payload["status"] in {"pass", "needs_work", "block"}
    assert payload["request"]["mode"] == "pull_request"
    assert payload["capabilities"]["expected"]
    assert "api_contract" in payload["capabilities"]["expected"]
    assert "markdown" in payload
    assert "packet" in payload


def test_app_bridge_cli_runs(tmp_path: Path) -> None:
    _make_repo(tmp_path)

    exit_code = main(["app-review", str(tmp_path), "--mode", "pull_request", "--files", "src/app.py,tests/test_app.py"])

    assert exit_code == 0


def test_app_bridge_cli_accepts_request_file(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    request_file = tmp_path / "sergeant-request.json"
    request_file.write_text(json.dumps({"root": str(tmp_path), "mode": "changed_files", "changed_files": ["src/app.py", "tests/test_app.py"]}), encoding="utf-8")

    exit_code = main(["app-review", "--request-file", str(request_file)])

    assert exit_code == 0


def test_app_bridge_keeps_v1_payload_when_v2_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_repo(tmp_path)

    def fail_v2(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise RuntimeError("planned v2 failure")

    monkeypatch.setattr(app_bridge, "run_v2_mission", fail_v2)

    payload = handle_app_review_request({"root": str(tmp_path), "mode": "pull_request", "changed_files": ["src/app.py"]})

    assert payload["ok"] is True
    assert payload["schema_version"] == CONTRACT_VERSION
    assert payload["v2"]["ok"] is False
    assert payload["v2"]["error"] == "v2_mission_failed"
    assert payload["v2"]["error_type"] == "RuntimeError"
