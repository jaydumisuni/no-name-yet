from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from main_review.review_benchmark import (
    CASE_SCHEMA,
    ReviewBenchmarkError,
    _mode_environment,
    extract_predictions,
    main,
    run_case,
    validate_case,
)


def _case(*, expected_findings: list[dict] | None = None, expected_verdict: str = "APPROVE") -> dict:
    return {
        "schema_version": CASE_SCHEMA,
        "id": "blind-case",
        "title": "Blind case",
        "changed_files": ["src/app.py"],
        "files": [
            {"path": "pyproject.toml", "content": "[project]\nname='case'\nversion='0.0.0'\n"},
            {"path": "README.md", "content": "# Case\n"},
            {"path": ".github/workflows/ci.yml", "content": "name: ci\non: [push]\n"},
            {"path": "src/app.py", "content": "def value():\n    return 1\n"},
            {"path": "tests/test_app.py", "content": "def test_value():\n    assert True\n"},
        ],
        "expected_verdict": expected_verdict,
        "expected_findings": expected_findings or [],
    }


def _empty_packet(verdict: str = "APPROVE") -> dict:
    return {
        "verdict": {"verdict": verdict},
        "repository_review": {"verdict": "PASS", "blocking_findings": [], "major_findings": [], "minor_findings": []},
        "diff_review": {"verdict": "PASS", "blocking_findings": [], "major_findings": [], "minor_findings": []},
        "capability_review": {"verdict": "PASS", "findings": []},
        "cpl_review": {"status": "disabled", "passes": [], "findings": []},
    }


def test_blind_case_never_materializes_expected_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_phrase = "hidden answer phrase that must never enter the repository"
    payload = _case(expected_findings=[{
        "id": "hidden-answer",
        "category": "architecture",
        "severity": "major",
        "paths": ["src/app.py"],
        "keywords": expected_phrase.split(),
    }], expected_verdict="APPROVE")

    def fake_review(root: Path, *, changed_files: list[str], external_review_file=None):
        materialized = {
            path.relative_to(root).as_posix(): path.read_text(encoding="utf-8", errors="ignore")
            for path in root.rglob("*")
            if path.is_file()
        }
        assert set(materialized) == {item["path"] for item in payload["files"]}
        assert expected_phrase not in "\n".join(materialized.values())
        assert changed_files == ["src/app.py"]
        return _empty_packet()

    monkeypatch.setattr("main_review.review_benchmark.run_independent_pr_review", fake_review)
    result = run_case(payload, mode="deterministic")

    assert result.false_negative_count == 1
    assert result.prediction_count == 0


def test_benchmark_scores_grounded_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _case(expected_findings=[{
        "id": "unsafe-query",
        "category": "security_taint",
        "severity": "major",
        "paths": ["src/app.py"],
        "line_start": 2,
        "line_end": 2,
        "root_cause": "unsafe-data-flow",
        "keywords": ["unsafe", "query", "input"],
    }], expected_verdict="REQUEST_CHANGES")

    packet = _empty_packet("REQUEST_CHANGES")
    packet["capability_review"] = {"verdict": "NEEDS WORK", "findings": [{
        "capability": "security_taint",
        "severity": "major",
        "message": "Unsafe input reaches query execution.",
        "evidence": "Request input is used by query without validation.",
        "path": "src/app.py",
        "line_start": 2,
        "line_end": 2,
        "root_cause": "unsafe-data-flow",
        "confidence": 0.9,
    }]}
    monkeypatch.setattr("main_review.review_benchmark.run_independent_pr_review", lambda *args, **kwargs: packet)

    result = run_case(payload, mode="deterministic", match_threshold=0.5)

    assert result.true_positive_count == 1
    assert result.false_positive_count == 0
    assert result.precision == 1.0
    assert result.recall == 1.0
    assert result.path_accuracy == 1.0
    assert result.line_accuracy == 1.0
    assert result.verdict_correct is True


def test_prediction_extraction_deduplicates_same_finding() -> None:
    finding = {
        "capability": "data_flow",
        "severity": "major",
        "message": "Unsafe data flow.",
        "evidence": "Input reaches sink.",
        "path": "src/api.py",
        "line_start": 4,
    }
    packet = _empty_packet("REQUEST_CHANGES")
    packet["capability_review"] = {"findings": [finding, dict(finding)]}

    predictions, valid_count = extract_predictions(packet)

    assert valid_count == 2
    assert len(predictions) == 1


def test_filtered_note_does_not_inflate_duplicate_denominator(monkeypatch: pytest.MonkeyPatch) -> None:
    finding = {
        "capability": "data_flow",
        "severity": "major",
        "message": "Unsafe data flow.",
        "evidence": "Input reaches sink.",
        "path": "src/app.py",
        "line_start": 2,
    }
    note = {
        "capability": "data_flow",
        "severity": "note",
        "message": "Context only.",
        "evidence": "No actionable defect.",
        "path": "src/app.py",
    }
    packet = _empty_packet("REQUEST_CHANGES")
    packet["capability_review"] = {"findings": [finding, note]}
    predictions, valid_count = extract_predictions(packet)
    assert valid_count == 1
    assert len(predictions) == 1

    payload = _case(expected_findings=[{
        "id": "unsafe-flow",
        "category": "data_flow",
        "severity": "major",
        "paths": ["src/app.py"],
        "line_start": 2,
        "keywords": ["unsafe", "data", "flow"],
    }], expected_verdict="REQUEST_CHANGES")
    monkeypatch.setattr("main_review.review_benchmark.run_independent_pr_review", lambda *args, **kwargs: packet)
    result = run_case(payload, mode="deterministic", match_threshold=0.5)
    assert result.duplicate_rate == 0.0


def test_mode_environment_restores_process_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERGEANT_CPL_POLICY", "preferred")
    monkeypatch.delenv("SERGEANT_CPL_ENABLED", raising=False)

    with _mode_environment("one-model"):
        assert os.environ["SERGEANT_CPL_ENABLED"] == "true"
        assert os.environ["SERGEANT_CPL_POLICY"] == "required"
        assert os.environ["SERGEANT_CPL_MAX_COUNCIL_MEMBERS"] == "1"
        assert os.environ["SERGEANT_CPL_MAX_ROUNDS"] == "1"

    assert os.environ["SERGEANT_CPL_POLICY"] == "preferred"
    assert "SERGEANT_CPL_ENABLED" not in os.environ


def test_case_validation_rejects_answer_or_changed_path_smuggling() -> None:
    payload = _case()
    payload["changed_files"] = ["../answer-key.json"]
    with pytest.raises(ReviewBenchmarkError, match="changed_files"):
        validate_case(payload)


def test_benchmark_cli_writes_machine_readable_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    case_path = tmp_path / "case.json"
    case_path.write_text(json.dumps(_case()), encoding="utf-8")
    output = tmp_path / "result.json"
    monkeypatch.setattr("main_review.review_benchmark.run_independent_pr_review", lambda *args, **kwargs: _empty_packet())

    code = main([str(case_path), "--output", str(output), "--pretty"])

    assert code == 0
    saved = json.loads(output.read_text(encoding="utf-8"))
    printed = json.loads(capsys.readouterr().out)
    assert saved == printed
    assert saved["blind"] is True
    assert saved["passed"] is True
