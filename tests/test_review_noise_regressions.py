from __future__ import annotations

import json
from pathlib import Path

from main_review.capability_engine import run_capability_engine
from main_review.capability_policy import normalize_capability_review
from main_review.diff_policy import normalize_diff_review
from main_review.diff_review import review_changed_files
from main_review.review_scope import scope_repository_review


def test_capability_engine_excludes_evaluation_fixture_payloads(tmp_path: Path) -> None:
    (tmp_path / "review-benchmarks" / "blind").mkdir(parents=True)
    fixture = tmp_path / "review-benchmarks" / "blind" / "unsafe.json"
    fixture.write_text(json.dumps({
        "files": [{
            "path": "src/api.py",
            "content": "value = request.args.get('id')\ndb.query(value)\n",
        }],
        "expected_findings": [{"message": "unsafe query"}],
    }), encoding="utf-8")

    result = run_capability_engine(tmp_path, ["review-benchmarks/blind/unsafe.json"])

    assert result["verdict"] == "PASS"
    assert result["findings"] == []
    assert result["evaluation_files_excluded"] == ["review-benchmarks/blind/unsafe.json"]
    assert result["reviewable_changed_files"] == []


def test_diff_and_capability_layers_share_one_proof_gap_identity(tmp_path: Path) -> None:
    diff = normalize_diff_review(review_changed_files(["src/app.py"]), tmp_path, ["src/app.py"])
    capability = normalize_capability_review({
        "verdict": "NEEDS WORK",
        "changed_files": ["src/app.py"],
        "findings": [{
            "capability": "test_impact",
            "severity": "major",
            "message": "Implementation changed without changed tests in the same PR.",
            "evidence": "One implementation file changed and no test file changed.",
        }],
    }, tmp_path)

    diff_finding = diff["evidence"]["findings"][0]
    capability_finding = capability["findings"][0]
    assert diff_finding["category"] == capability_finding["capability"] == "test_impact"
    assert diff_finding["message"] == capability_finding["message"]
    assert diff_finding["root_cause"] == capability_finding["root_cause"] == "proof-gap"


def test_generic_api_adjacent_filename_is_context_not_a_defect(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "api.py").write_text("def helper(): return True\n", encoding="utf-8")
    normalized = normalize_capability_review({
        "verdict": "PASS",
        "changed_files": ["src/api.py"],
        "findings": [{
            "capability": "api_contract",
            "severity": "minor",
            "path": "src/api.py",
            "message": "API-adjacent file changed; check callers and contracts.",
            "evidence": "Path name indicates an API-adjacent surface.",
        }],
    }, tmp_path)

    finding = normalized["findings"][0]
    assert finding["severity"] == "note"
    assert finding["context_signal"] is True
    assert finding["direct_evidence"] is False
    assert normalized["verdict"] == "PASS"


def test_capability_findings_receive_canonical_root_causes(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "report.py").write_text(
        "def pairs(rows):\n    for left in rows:\n        for right in rows:\n            yield left, right\n",
        encoding="utf-8",
    )
    normalized = normalize_capability_review({
        "verdict": "PASS",
        "changed_files": ["src/report.py"],
        "findings": [{
            "capability": "performance",
            "severity": "minor",
            "path": "src/report.py",
            "message": "Nested iteration pattern may create scaling risk.",
            "evidence": "Nested loops were detected.",
        }],
    }, tmp_path)

    assert normalized["findings"][0]["root_cause"] == "runtime-risk"


def test_parameterized_query_suppresses_lexical_taint_findings(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "api.py").write_text(
        "def get_user(request, db):\n"
        "    user_id = request.args.get('id')\n"
        "    return db.query(\"SELECT * FROM users WHERE id = ?\", [user_id])\n",
        encoding="utf-8",
    )
    normalized = normalize_capability_review({
        "verdict": "NEEDS WORK",
        "changed_files": ["src/api.py"],
        "findings": [
            {
                "capability": "data_flow",
                "severity": "major",
                "path": "src/api.py",
                "message": "User-controlled input appears near a risky sink.",
                "evidence": "Input and query patterns coexist.",
            },
            {
                "capability": "security_taint",
                "severity": "major",
                "path": "src/api.py",
                "message": "Potential tainted input path needs validation review.",
                "evidence": "Input and query patterns coexist.",
            },
        ],
    }, tmp_path)

    assert normalized["verdict"] == "PASS"
    assert {item["severity"] for item in normalized["findings"]} == {"note"}
    assert all(item["safe_binding_signal"] is True for item in normalized["findings"])


def test_uncontained_request_path_creates_two_grounded_findings(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "files.py").write_text(
        "from pathlib import Path\n\n"
        "BASE = Path('/srv/files')\n\n"
        "def download(request):\n"
        "    name = request.args.get('name')\n"
        "    return open(BASE / name, 'rb')\n",
        encoding="utf-8",
    )

    normalized = normalize_capability_review({
        "verdict": "PASS",
        "changed_files": ["src/files.py"],
        "findings": [],
    }, tmp_path)

    assert normalized["verdict"] == "NEEDS WORK"
    assert len(normalized["findings"]) == 2
    assert {item["capability"] for item in normalized["findings"]} == {"data_flow", "security_taint"}
    assert {item["root_cause"] for item in normalized["findings"]} == {"unsafe-file-access"}
    assert {item["line_start"] for item in normalized["findings"]} == {7}


def test_privileged_route_without_guard_creates_authorization_finding(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "admin_api.py").write_text(
        "def delete_user(request):\n"
        "    return {'deleted': request.params['id']}\n\n"
        "app.delete('/admin/users/:id', delete_user)\n",
        encoding="utf-8",
    )

    normalized = normalize_capability_review({
        "verdict": "PASS",
        "changed_files": ["src/admin_api.py"],
        "findings": [],
    }, tmp_path)

    assert normalized["verdict"] == "NEEDS WORK"
    finding = normalized["findings"][0]
    assert finding["capability"] == "security_taint"
    assert finding["root_cause"] == "authorization-gap"
    assert finding["line_start"] == 4


def test_battle_rule_source_matches_are_suppressed_not_scoped() -> None:
    review = {
        "verdict": {"verdict": "PASS"},
        "evidence": {"findings": [
            {
                "provider": "battle-aware-checker",
                "severity": "minor",
                "category": "testing",
                "path": "main_review/evidence.py",
                "message": "Duplicate tests should be removed or parameterized.",
            },
            {
                "provider": "documentation-checker",
                "severity": "minor",
                "category": "documentation",
                "path": "README.md",
                "message": "A real changed-scope documentation finding.",
            },
        ]},
    }

    scoped = scope_repository_review(review, ["main_review/evidence.py", "README.md"])

    assert scoped["scope"]["suppressed_finding_count"] == 1
    assert scoped["scope"]["scoped_finding_count"] == 1
    assert scoped["suppressed"]["sample"][0]["path"] == "main_review/evidence.py"
