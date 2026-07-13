from __future__ import annotations

from main_review.cpl_reasoning import plan_cpl_assignments, specialist_system_prompt
from main_review.squad import run_squad_review


def test_cpl_assignments_support_permanent_officers(monkeypatch) -> None:
    monkeypatch.setenv("SERGEANT_CPL_DEPTH", "maximum")
    monkeypatch.setenv("SERGEANT_CPL_MAX_PASSES", "8")

    assignments = plan_cpl_assignments([], {}, primary_verdict="PASS")
    by_specialist = {item.specialist: item for item in assignments}

    assert by_specialist["correctness"].officer == "Engineer"
    assert by_specialist["architecture"].officer == "Engineer"
    assert by_specialist["tests_contracts"].officer == "Engineer"
    assert by_specialist["security"].officer == "Medic"
    assert by_specialist["performance_concurrency"].officer == "Mechanic"

    prompt = specialist_system_prompt("base", by_specialist["security"])
    assert "Supported permanent officer: Medic" in prompt
    assert "replaceable model-powered support bot" in prompt
    assert "Do not impersonate Cpl or replace the permanent officer" in prompt


def test_squad_receives_shared_and_targeted_cpl_support() -> None:
    cpl = {
        "status": "completed",
        "verdict": "NEEDS WORK",
        "confidence": 0.88,
        "route": {"provider": "test", "model": "provider/glm"},
        "coverage": {"files_reviewed": ["src/app.py"]},
        "unanswered_questions": [],
        "findings": [{"severity": "major", "message": "contract drift", "confidence": 0.9}],
        "reasoning_plan": [
            {
                "specialist": "architecture",
                "officer": "Engineer",
                "officer_role": "Technical Construction",
                "title": "Architecture Support Bot",
                "mission": "Help Engineer inspect contracts.",
                "model": "provider/qwen",
            }
        ],
        "passes": [
            {
                "specialist": "generalist",
                "model": "provider/glm",
                "provider": "test",
                "verdict": "PASS",
                "confidence": 0.8,
                "findings": [],
            },
            {
                "specialist": "architecture",
                "model": "provider/qwen",
                "provider": "test",
                "verdict": "NEEDS WORK",
                "confidence": 0.9,
                "findings": [{"severity": "major", "message": "contract drift", "confidence": 0.9}],
            },
        ],
    }
    packet = {
        "repository_review": {"verdict": "PASS"},
        "capability_review": {"findings": []},
        "review_intelligence": {"ranked_findings": []},
        "cpl_review": cpl,
    }

    result = run_squad_review(packet, {"classified_findings": []}, {}, {"verdict": "TRUSTED_WITH_WATCH"})
    reports = {report["agent"]: report for report in result["reports"]}

    assert len(reports) == 10
    assert result["cpl_command"]["role"].startswith("senior field reasoning")
    assert all(report["cpl_support"] for report in reports.values())
    assert any(unit["kind"] == "officer_support_bot" for unit in reports["engineer"]["cpl_support"])
    assert not any(unit["kind"] == "officer_support_bot" for unit in reports["medic"]["cpl_support"])
    assert reports["engineer"]["status"] == "needs_work"
    assert "Cpl amplifies" in result["summary"]["rule"]
