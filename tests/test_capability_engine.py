from __future__ import annotations

from pathlib import Path

from main_review.capability_engine import run_capability_engine
from main_review.pr_reviewer import render_pr_review_markdown, run_independent_pr_review


def _write_project(root: Path) -> None:
    (root / "package.json").write_text('{"scripts":{"test":"node tests/test_api.js"}}\n', encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "db.js").write_text(
        "export function queryDb(sql) { return query(sql); }\n",
        encoding="utf-8",
    )
    (root / "src" / "api.js").write_text(
        "import { queryDb } from './db';\n"
        "export function getUser(req) {\n"
        "  const sql = `SELECT * FROM users WHERE id=${req.query.id}`;\n"
        "  return queryDb(sql);\n"
        "}\n"
        "app.get('/users/:id', getUser);\n",
        encoding="utf-8",
    )
    (root / "src" / "client.js").write_text(
        "export async function loadUser() { return fetch('/users/1'); }\n",
        encoding="utf-8",
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_api.js").write_text("assert.ok(true);\n", encoding="utf-8")


def test_capability_engine_reports_tier1_signals(tmp_path: Path) -> None:
    _write_project(tmp_path)

    report = run_capability_engine(tmp_path, changed_files=["src/db.js", "src/api.js"])

    assert report["verdict"] in {"NEEDS WORK", "BLOCK"}
    assert report["capability_status"]["cross_file"] == "active"
    assert report["capability_status"]["data_flow"] == "active"
    assert report["capability_status"]["call_graph"] == "active"
    capabilities = {finding["capability"] for finding in report["findings"]}
    assert "security_taint" in capabilities
    assert "api_contract" in capabilities
    assert "test_impact" in capabilities


def test_sergeant_review_includes_capability_review(tmp_path: Path) -> None:
    _write_project(tmp_path)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")

    packet = run_independent_pr_review(tmp_path, changed_files=["src/api.js"])
    rendered = render_pr_review_markdown(packet)

    assert "capability_review" in packet
    assert packet["capability_review"]["capability_status"]["api_contract"] == "active"
    assert "Tier 1 capabilities" in rendered
    assert "Sergeant Review" in rendered
