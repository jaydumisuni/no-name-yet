from __future__ import annotations

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


def test_demonstrated_defect_capability_keeps_blocking_severity() -> None:
    packet = {
        "verdict": "NEEDS WORK",
        "findings": [
            {
                "capability": "api_contract",
                "severity": "major",
                "path": "src/api.py",
                "message": "Changed route has no contract proof.",
                "evidence": "POST /orders changed without matching tests.",
            },
            {
                "capability": "security_taint",
                "severity": "blocker",
                "path": "src/auth.py",
                "message": "Untrusted input reaches command execution.",
                "evidence": "request input and exec were detected.",
            },
        ],
    }

    normalized = normalize_capability_review(packet)

    assert normalized["verdict"] == "BLOCK"
    assert normalized["findings"] == packet["findings"]
    assert normalized["policy_adjustments"] == []
