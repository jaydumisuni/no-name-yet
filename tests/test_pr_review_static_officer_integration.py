from __future__ import annotations

import json
from pathlib import Path

from main_review.cli import main


def _make_verified_repo(root: Path, source: str) -> None:
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (root / "main_review").mkdir()
    (root / "tests").mkdir()
    (root / "tests" / "test_server.py").write_text("def test_placeholder(): assert True\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "server.py").write_text(source, encoding="utf-8")
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (root / "docs").mkdir()
    for name in (
        "12-external-review-learning-loop.md",
        "19-thetechguy-engineering-standard.md",
        "20-clean-clone-proof.md",
        "21-open-source-reviewer-patterns.md",
    ):
        (root / "docs" / name).write_text("# Doc\n", encoding="utf-8")


def _run_cli(tmp_path: Path, monkeypatch, capsys) -> dict:
    monkeypatch.setenv("SERGEANT_LLM_ENABLED", "false")
    monkeypatch.setenv("SERGEANT_CPL_ENABLED", "false")
    monkeypatch.setenv("SERGEANT_CPL_POLICY", "disabled")
    file_list = tmp_path / "changed-files.txt"
    file_list.write_text("src/server.py\ntests/test_server.py\n", encoding="utf-8")
    assert main(["pr-review", str(tmp_path), "--file-list", str(file_list)]) == 0
    return json.loads(capsys.readouterr().out)


def test_documented_pr_review_cli_admits_resource_claim_after_await(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _make_verified_repo(
        tmp_path,
        """
async def start(connections, caller, payload, session_id):
    for candidate in connections:
        if candidate is not caller and candidate.websocket and not candidate.session_id:
            await candidate.websocket.send_text(payload)
            candidate.session_id = session_id
""",
    )

    packet = _run_cli(tmp_path, monkeypatch, capsys)
    roots = {
        str(item.get("root_cause"))
        for item in packet.get("officer_council", {}).get("admitted_findings", [])
        if isinstance(item, dict)
    }

    assert "resource-claim-after-await" in roots
    assert packet["verdict"]["verdict"] == "REQUEST_CHANGES"
    assert packet["capability_review"]["static_invariant_review"]["executed_project_code"] is False


def test_documented_pr_review_cli_keeps_claim_before_await_clean(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _make_verified_repo(
        tmp_path,
        """
async def start(connections, caller, payload, session_id):
    for candidate in connections:
        if candidate is not caller and candidate.websocket and not candidate.session_id:
            candidate.session_id = session_id
            try:
                await candidate.websocket.send_text(payload)
            except Exception:
                candidate.session_id = None
""",
    )

    packet = _run_cli(tmp_path, monkeypatch, capsys)
    roots = {
        str(item.get("root_cause"))
        for item in packet.get("officer_council", {}).get("admitted_findings", [])
        if isinstance(item, dict)
    }

    assert "resource-claim-after-await" not in roots
