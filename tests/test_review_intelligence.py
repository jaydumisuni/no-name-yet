from __future__ import annotations

from pathlib import Path

from main_review.pr_reviewer import render_pr_review_markdown, run_independent_pr_review
from main_review.review_intelligence import run_review_intelligence


def test_review_intelligence_ranks_and_groups_findings() -> None:
    packet = {"capability_review": {"findings": [
        {"capability": "security_taint", "severity": "major", "message": "Potential unsafe input path needs validation review.", "evidence": "Input source and sensitive operation are both present.", "confidence": 0.7, "path": "src/api.py", "related_paths": ["src/db.py"]},
        {"capability": "security_taint", "severity": "major", "message": "Potential unsafe input path needs validation review.", "evidence": "Input source and sensitive operation are both present.", "confidence": 0.7, "path": "src/api.py", "related_paths": ["src/db.py"]},
        {"capability": "test_impact", "severity": "major", "message": "Implementation changed without changed tests in the same PR.", "evidence": "0 changed test files.", "confidence": 0.78},
    ]}}

    result = run_review_intelligence(packet)

    assert result["verdict"] == "NEEDS WORK"
    assert result["finding_count"] == 2
    assert "unsafe-data-flow" in result["root_causes"]
    assert result["ranked_findings"][0]["priority"] >= result["ranked_findings"][1]["priority"]
    assert result["ranked_findings"][0]["why_it_matters"]
    assert result["ranked_findings"][0]["safer_alternative"]
    assert result["trace"]


def _write_project(root: Path) -> None:
    (root / "package.json").write_text('{"scripts":{"test":"node tests/test_api.js"}}\n', encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "api.js").write_text(
        "export function getUser(req) {\n"
        "  const sql = `SELECT * FROM users WHERE id=${req.query.id}`;\n"
        "  return query(sql);\n"
        "}\n"
        "app.get('/users/:id', getUser);\n",
        encoding="utf-8",
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_api.js").write_text("assert.ok(true);\n", encoding="utf-8")
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")


def test_pr_review_includes_tier2_review_intelligence(tmp_path: Path) -> None:
    _write_project(tmp_path)

    packet = run_independent_pr_review(tmp_path, changed_files=["src/api.js"])
    rendered = render_pr_review_markdown(packet)

    assert "review_intelligence" in packet
    assert packet["review_intelligence"]["quality_score"] <= 100
    assert "Review intelligence verdict" in rendered
    assert "Tier 2 ranked findings" in rendered
