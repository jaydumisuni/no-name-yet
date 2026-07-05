from __future__ import annotations

from pathlib import Path

from main_review.app_bridge import handle_app_review_request
from main_review.graduation import run_graduation_benchmark, summarize_graduation


def test_graduation_benchmark_scores_and_gaps() -> None:
    sergeant = {
        "name": "Sergeant",
        "metrics": {
            "real_bugs_found": 0.9,
            "false_positive_control": 0.9,
            "explanation_quality": 0.9,
            "architecture_reasoning": 0.9,
            "security_findings": 0.8,
            "regression_prediction": 0.9,
            "documentation_consistency": 0.9,
        },
    }
    reference = {"name": "External Benchmark", "metrics": {"real_bugs_found": 0.8, "false_positive_control": 0.85}}

    result = run_graduation_benchmark(sergeant, reference)
    markdown = summarize_graduation(result)

    assert result["verdict"] in {"GRADUATED", "TRUSTED_WITH_WATCH", "NEEDS_MORE_PROOF"}
    assert result["sergeant"]["score"] > result["reference"]["score"]
    assert "Sergeant Graduation Benchmark" in markdown


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


def test_app_bridge_returns_graduation_packet(tmp_path: Path) -> None:
    _make_repo(tmp_path)

    payload = handle_app_review_request(
        {
            "root": str(tmp_path),
            "mode": "pull_request",
            "changed_files": ["src/app.py", "tests/test_app.py"],
            "reference_benchmark": {"name": "External Benchmark", "metrics": {"real_bugs_found": 0.5}},
        }
    )

    assert payload["ok"] is True
    assert "graduation" in payload
    assert "graduation_markdown" in payload
    assert payload["graduation"]["rule"].startswith("Sergeant graduates")
