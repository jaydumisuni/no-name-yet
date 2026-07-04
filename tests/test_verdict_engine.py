from __future__ import annotations

from pathlib import Path

from main_review.verdict import decide_verdict, review_repository


def test_verdict_blocks_on_blocker() -> None:
    report = decide_verdict(
        {
            "findings": [
                {"severity": "blocker", "category": "security", "message": "secret"},
                {"severity": "major", "category": "testing", "message": "missing tests"},
            ]
        }
    )

    assert report.verdict == "BLOCK"
    assert report.blocking_findings
    assert report.suggested_next_action.startswith("Fix blocker")


def test_verdict_needs_work_on_major_without_blocker() -> None:
    report = decide_verdict({"findings": [{"severity": "major", "category": "testing", "message": "missing tests"}]})

    assert report.verdict == "NEEDS WORK"
    assert report.major_findings


def test_verdict_passes_with_minor_or_no_findings() -> None:
    minor_report = decide_verdict({"findings": [{"severity": "minor", "category": "documentation", "message": "readme"}]})
    clean_report = decide_verdict({"findings": []})

    assert minor_report.verdict == "PASS"
    assert clean_report.verdict == "PASS"


def test_review_repository_returns_block_for_secret(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "config.py").write_text("TOKEN='1234567890abcdef'\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_config.py").write_text("def test_ok(): assert True\n", encoding="utf-8")

    result = review_repository(tmp_path)

    assert result["verdict"]["verdict"] == "BLOCK"
    assert result["evidence"]["finding_count"] >= 1
