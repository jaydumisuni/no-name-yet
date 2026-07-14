from __future__ import annotations

from pathlib import Path

from main_review.capability_policy import normalize_capability_review


def test_dependency_impact_alone_does_not_block_review() -> None:
    packet = {
        "verdict": "NEEDS WORK",
        "findings": [
            {
                "capability": "call_graph",
                "severity": "major",
                "path": "main_review/pr_reviewer.py",
                "message": "Changed exported symbols are called from other files.",
                "evidence": "Detected callers in app_bridge.py and github_bot.py.",
                "related_paths": ["main_review/app_bridge.py", "main_review/github_bot.py"],
            },
            {
                "capability": "cross_file",
                "severity": "major",
                "path": "main_review/llm_review.py",
                "message": "Changed file has dependent modules that may be affected.",
                "evidence": "One dependent module imports this file.",
                "related_paths": ["main_review/pr_reviewer.py"],
            },
        ],
    }

    normalized = normalize_capability_review(packet)

    assert normalized["verdict"] == "PASS"
    assert {item["severity"] for item in normalized["findings"]} == {"minor"}
    assert all(item["impact_signal"] is True for item in normalized["findings"])
    assert len(normalized["policy_adjustments"]) == 2


def test_high_blast_radius_downgrades_only_with_focused_changed_test(tmp_path: Path) -> None:
    (tmp_path / "main_review").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "main_review" / "production_hardening.py").write_text("def policy(): return True\n", encoding="utf-8")
    (tmp_path / "tests" / "test_production_hardening.py").write_text(
        "from main_review.production_hardening import policy\n\ndef test_policy(): assert policy()\n",
        encoding="utf-8",
    )
    packet = {
        "verdict": "NEEDS WORK",
        "changed_files": ["main_review/production_hardening.py", "tests/test_production_hardening.py"],
        "findings": [{
            "capability": "regression",
            "severity": "major",
            "path": "main_review/production_hardening.py",
            "message": "High blast-radius change may regress dependent behavior.",
            "evidence": "At least 5 files depend on this file.",
        }],
    }

    normalized = normalize_capability_review(packet, tmp_path)

    assert normalized["verdict"] == "PASS"
    assert normalized["findings"][0]["severity"] == "minor"
    assert normalized["findings"][0]["impact_signal"] is True
    assert normalized["findings"][0]["test_coverage_path"] == "tests/test_production_hardening.py"
    assert normalized["policy_adjustments"][0]["coverage_path"] == "tests/test_production_hardening.py"


def test_high_blast_radius_remains_major_without_targeted_changed_test(tmp_path: Path) -> None:
    (tmp_path / "main_review").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "main_review" / "production_hardening.py").write_text("def policy(): return True\n", encoding="utf-8")
    (tmp_path / "tests" / "test_unrelated.py").write_text("def test_other(): assert True\n", encoding="utf-8")
    packet = {
        "verdict": "NEEDS WORK",
        "changed_files": ["main_review/production_hardening.py", "tests/test_unrelated.py"],
        "findings": [{
            "capability": "regression",
            "severity": "major",
            "path": "main_review/production_hardening.py",
            "message": "High blast-radius change may regress dependent behavior.",
            "evidence": "At least 5 files depend on this file.",
        }],
    }

    normalized = normalize_capability_review(packet, tmp_path)

    assert normalized["verdict"] == "NEEDS WORK"
    assert normalized["findings"] == packet["findings"]
    assert normalized["policy_adjustments"] == []


def test_lexical_taint_without_sensitive_sink_is_non_blocking(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "extension.js").write_text(
        "const env = {...process.env};\n"
        "const child = cp.spawn('python', ['sergeant.py'], {env, shell: false});\n",
        encoding="utf-8",
    )
    packet = {
        "verdict": "NEEDS WORK",
        "findings": [
            {
                "capability": "security_taint",
                "severity": "major",
                "path": "src/extension.js",
                "message": "Potential tainted input path needs validation review.",
                "evidence": "Input source and security-sensitive operation are both present.",
            }
        ],
    }

    normalized = normalize_capability_review(packet, tmp_path)

    assert normalized["verdict"] == "PASS"
    assert normalized["findings"][0]["severity"] == "note"
    assert normalized["findings"][0]["lexical_signal"] is True
    assert normalized["policy_adjustments"][0]["to"] == "note"


def test_demonstrated_security_sink_keeps_blocking_severity(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.py").write_text(
        "command = input('command: ')\nexec(command)\n",
        encoding="utf-8",
    )
    packet = {
        "verdict": "BLOCK",
        "findings": [
            {
                "capability": "security_taint",
                "severity": "blocker",
                "path": "src/auth.py",
                "message": "Untrusted input reaches command execution.",
                "evidence": "request input and exec were detected.",
            }
        ],
    }

    normalized = normalize_capability_review(packet, tmp_path)

    assert normalized["verdict"] == "BLOCK"
    assert normalized["findings"] == packet["findings"]
    assert normalized["policy_adjustments"] == []


def test_non_signal_demonstrated_defect_capability_keeps_blocking_severity() -> None:
    packet = {
        "verdict": "NEEDS WORK",
        "findings": [
            {
                "capability": "api_contract",
                "severity": "major",
                "path": "src/api.py",
                "message": "Changed route has no contract proof.",
                "evidence": "POST /orders changed without matching tests.",
            }
        ],
    }

    normalized = normalize_capability_review(packet)

    assert normalized["verdict"] == "NEEDS WORK"
    assert normalized["findings"] == packet["findings"]
    assert normalized["policy_adjustments"] == []
