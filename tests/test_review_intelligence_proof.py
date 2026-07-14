from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from main_review.battle_compare import run_battle_comparison
from main_review.capability_policy import normalize_capability_review
from main_review.evidence import BattleAwareEvidenceProvider
from main_review.review_intelligence import run_review_intelligence
from main_review.review_scope import scope_repository_review
from main_review.scanner import scan_repository


def test_empty_intelligence_is_not_misreported_as_perfect_quality() -> None:
    result = run_review_intelligence({"capability_review": {"findings": []}})

    assert result["verdict"] == "PASS"
    assert result["quality_score"] is None
    assert result["quality_score_evaluable"] is False
    assert result["promoted_count"] == 0


def test_generic_major_without_path_is_preserved_but_not_promoted() -> None:
    result = run_review_intelligence({"capability_review": {"findings": [{
        "capability": "architecture",
        "severity": "major",
        "message": "Architecture might be risky.",
        "evidence": "Generic architectural terms were detected.",
        "confidence": 0.7,
    }]}})

    assert result["verdict"] == "PASS"
    assert result["finding_count"] == 1
    assert result["promoted_count"] == 0
    assert result["ranked_findings"][0]["challenge_result"].startswith("weakened:")


def test_grounded_major_is_promoted_with_complete_review_explanation() -> None:
    result = run_review_intelligence({"capability_review": {"findings": [{
        "capability": "data_flow",
        "severity": "major",
        "message": "Untrusted request input reaches a query sink.",
        "evidence": "request.args value is interpolated into db.query.",
        "path": "src/api.py",
        "line_start": 3,
        "line_end": 3,
        "confidence": 0.92,
    }]}})

    finding = result["promoted_findings"][0]
    assert result["verdict"] == "NEEDS WORK"
    assert result["promoted_count"] == 1
    assert finding["trigger"]
    assert finding["consequence"]
    assert finding["safer_alternative"]
    assert finding["verification_test"]
    assert finding["evidence_strength"] >= 0.8
    assert finding["completeness_score"] >= 0.9


def test_capability_policy_adds_precise_sink_location(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "api.py").write_text(
        "def get(request, db):\n"
        "    value = request.args.get('id')\n"
        "    return db.query(f'SELECT * FROM users WHERE id = {value}')\n",
        encoding="utf-8",
    )
    packet = {
        "verdict": "NEEDS WORK",
        "changed_files": ["src/api.py"],
        "findings": [{
            "capability": "security_taint",
            "severity": "major",
            "path": "src/api.py",
            "message": "Input and sensitive sink coexist.",
            "evidence": "Request input and query execution are present.",
            "confidence": 0.8,
        }],
    }

    normalized = normalize_capability_review(packet, tmp_path)
    finding = normalized["findings"][0]

    assert finding["severity"] == "major"
    assert finding["line_start"] == 3
    assert finding["line_end"] == 3
    assert finding["evidence_ref"] == "src/api.py:3"
    assert finding["direct_evidence"] is True


def test_api_contract_downgrades_only_with_focused_changed_test(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "api.py").write_text("app.delete('/users/:id', delete_user)\n", encoding="utf-8")
    (tmp_path / "tests" / "test_api.py").write_text("from src.api import delete_user\n", encoding="utf-8")
    packet = {
        "verdict": "NEEDS WORK",
        "changed_files": ["src/api.py", "tests/test_api.py"],
        "findings": [{
            "capability": "api_contract",
            "severity": "major",
            "path": "src/api.py",
            "message": "Changed public route requires contract proof.",
            "evidence": "Public route marker detected.",
        }],
    }

    normalized = normalize_capability_review(packet, tmp_path)

    assert normalized["verdict"] == "PASS"
    assert normalized["findings"][0]["severity"] == "minor"
    assert normalized["findings"][0]["test_coverage_path"] == "tests/test_api.py"


def test_repository_scope_keeps_global_security_and_changed_path_only() -> None:
    repository_review = {
        "verdict": {"verdict": "BLOCK"},
        "evidence": {"findings": [
            {"severity": "minor", "category": "risk", "path": "old/deploy.yml", "message": "Old risk"},
            {"severity": "major", "category": "architecture", "path": "src/app.py", "message": "Changed risk"},
            {"severity": "blocker", "category": "security", "path": "unrelated/secret.txt", "message": "Secret"},
        ]},
    }

    scoped = scope_repository_review(repository_review, ["src/app.py"])

    assert scoped["scope"]["scoped_finding_count"] == 2
    assert scoped["scope"]["background_finding_count"] == 1
    assert scoped["verdict"]["verdict"] == "BLOCK"
    assert scoped["background"]["sample"][0]["path"] == "old/deploy.yml"


def test_battle_aware_rules_ignore_fixture_answer_prose(tmp_path: Path) -> None:
    (tmp_path / "battle-tests").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "battle-tests" / "answer.json").write_text(
        json.dumps({"answer": "NamedTemporaryFile requests.post files={ duplicate tests"}),
        encoding="utf-8",
    )
    (tmp_path / "src" / "plain.py").write_text("def value(): return 1\n", encoding="utf-8")

    findings = BattleAwareEvidenceProvider().collect(tmp_path, scan_repository(tmp_path))

    assert findings == []


@dataclass(frozen=True)
class FakeFile:
    filename: str
    patch: str


@dataclass(frozen=True)
class FakeDiff:
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    files: list[FakeFile]


def test_live_battle_does_not_fetch_existing_comments_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({
        "repository": "owner/repo",
        "pull_request": 12,
        "expected_sergeant_findings": [],
    }), encoding="utf-8")
    monkeypatch.setattr(
        "main_review.battle_compare.fetch_pr_diff_live",
        lambda *args, **kwargs: FakeDiff("owner/repo", 12, "base", "head", [FakeFile("src/app.py", "@@\n+plain change")]),
    )

    def comments_must_not_run(*args, **kwargs):
        raise AssertionError("existing reviewer comments leaked into blind battle")

    monkeypatch.setattr("main_review.battle_compare.fetch_pr_comments_live", comments_must_not_run)

    result = run_battle_comparison(fixture)

    assert result.files_reviewed == ["src/app.py"]
    assert all("excluded by default" in caveat for caveat in result.caveats if "review comments" in caveat)
