from __future__ import annotations

from pathlib import Path

from main_review.app_bridge import handle_app_review_request
from main_review.squad import run_squad_review


def test_squad_review_builds_all_agent_reports() -> None:
    packet = {
        "repository_review": {"verdict": "PASS"},
        "standard": {"passed": True},
        "capability_review": {
            "findings": [
                {"capability": "api_contract", "severity": "major", "message": "route drift", "confidence": 0.8},
                {"capability": "security_taint", "severity": "major", "message": "taint risk", "confidence": 0.75},
            ]
        },
        "review_intelligence": {
            "ranked_findings": [{"root_cause": "change-impact", "severity": "major", "message": "route drift", "confidence": 0.8}],
            "root_causes": {"change-impact": ["route drift"]},
        },
    }
    evidence = {"classified_findings": [{"category": "api_contract", "verdict": "NEEDS WORK", "message": "route drift", "confidence": 0.8}]}

    result = run_squad_review(packet, evidence, {}, {"verdict": "TRUSTED_WITH_WATCH", "delta": 0.1})

    assert result["summary"]["rule"].startswith("Specialists advise")
    assert len(result["reports"]) == 10
    assert {report["agent"] for report in result["reports"]} >= {"sergeant"} or "hermes" in {report["agent"] for report in result["reports"]}
    assert "engineer" in result["summary"]["needs_work_agents"] or "medic" in result["summary"]["needs_work_agents"]


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


def test_app_bridge_returns_squad_packet(tmp_path: Path) -> None:
    _make_repo(tmp_path)

    payload = handle_app_review_request({"root": str(tmp_path), "mode": "pull_request", "changed_files": ["src/app.py", "tests/test_app.py"]})

    assert payload["ok"] is True
    assert "squad" in payload
    assert payload["squad"]["summary"]["rule"].startswith("Specialists advise")
    assert any(report["agent"] == "hermes" for report in payload["squad"]["reports"])
