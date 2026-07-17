from __future__ import annotations

from pathlib import Path

from main_review.languages import classify_role, detect_language, is_high_risk_path
from main_review.scanner import scan_repository


def test_language_detection_is_broad_and_includes_r() -> None:
    cases = {
        "app.py": "Python",
        "app.tsx": "TypeScript",
        "main.go": "Go",
        "lib.rs": "Rust",
        "analysis.R": "R",
        "report.Rmd": "R",
        "Dockerfile": "Dockerfile",
        "script.ps1": "PowerShell",
        "query.sql": "SQL",
        "unknown.xyz": "Unknown",
    }

    for path, expected in cases.items():
        assert detect_language(path) == expected


def test_role_classifier_marks_docs_tests_manifests_and_risky_paths() -> None:
    assert classify_role("README.md") == "documentation"
    assert classify_role("tests/test_app.py") == "test"
    assert classify_role("package.json") == "manifest"
    assert classify_role("Service.csproj") == "manifest"
    assert classify_role("Package.swift") == "manifest"
    assert classify_role(".github/workflows/ci.yml") == "infrastructure"
    assert classify_role("src/app.py") == "source"
    assert is_high_risk_path(".github/workflows/ci.yml") is True


def test_scan_repository_builds_context_packet(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "analysis").mkdir()
    (tmp_path / "analysis" / "model.R").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")

    insight = scan_repository(tmp_path)
    payload = insight.to_dict()

    assert payload["total_files"] == 6
    assert payload["languages"]["Python"] == 2
    assert payload["languages"]["R"] == 1
    assert "README.md" in payload["docs"]
    assert "tests/test_app.py" in payload["tests"]
    assert "pyproject.toml" in payload["manifests"]
    assert ".github/workflows/ci.yml" in payload["high_risk_files"]
