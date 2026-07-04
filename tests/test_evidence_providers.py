from __future__ import annotations

from pathlib import Path

from main_review.evidence import collect_evidence


def _messages(payload: dict[str, object]) -> list[str]:
    return [finding["message"] for finding in payload["findings"]]  # type: ignore[index]


def test_evidence_detects_missing_tests_and_docs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    payload = collect_evidence(tmp_path)
    messages = _messages(payload)

    assert payload["finding_count"] == 2
    assert "Source files exist but no tests were detected." in messages
    assert "No documentation files were detected." in messages


def test_evidence_detects_secret_and_high_risk_path(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "config.py").write_text("API_KEY='1234567890abcdef'\n", encoding="utf-8")

    payload = collect_evidence(tmp_path)
    findings = payload["findings"]  # type: ignore[assignment]

    assert any(finding["severity"] == "blocker" and finding["category"] == "security" for finding in findings)  # type: ignore[index]
    assert any(finding["provider"] == "risk-path-checker" for finding in findings)  # type: ignore[index]


def test_clean_small_repository_has_no_major_findings(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")

    payload = collect_evidence(tmp_path)
    findings = payload["findings"]  # type: ignore[assignment]

    assert not [finding for finding in findings if finding["severity"] in {"blocker", "major"}]  # type: ignore[index]
