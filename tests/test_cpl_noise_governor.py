from __future__ import annotations

from typing import Any

import pytest

from main_review import llm_review
from main_review.cpl_noise import findings_overlap, reconcile_cpl_findings
from main_review.cpl_runtime import _effective_passes
from main_review.llm_provider import LLMProviderError, LLMRoute
from main_review.pr_reviewer import _decide
from main_review.review_benchmark import extract_predictions


def deterministic_shell() -> dict[str, Any]:
    return {
        "capability": "security_taint",
        "category": "security_taint",
        "severity": "major",
        "message": "Potential tainted input path needs validation review.",
        "evidence": "Input source and security-sensitive operation are both present.",
        "path": "src/jobs.py",
        "line_start": 5,
        "line_end": 5,
        "root_cause": "unsafe-data-flow",
    }


def cpl_shell() -> dict[str, Any]:
    return {
        "category": "security",
        "severity": "blocker",
        "message": "User-controlled input reaches subprocess.run with shell=True.",
        "evidence": "return subprocess.run(command, shell=True)",
        "evidence_verified": True,
        "path": "src/jobs.py",
        "line_start": 5,
        "line_end": 5,
        "supporting_models": ["model-a", "model-b"],
    }


def test_cross_source_overlap_maps_specific_shell_defect_to_deterministic_data_flow() -> None:
    assert findings_overlap(cpl_shell(), deterministic_shell()) is True


def test_reconciliation_keeps_confirmation_but_does_not_create_duplicate_action() -> None:
    result = reconcile_cpl_findings(
        {"status": "completed", "verdict": "BLOCK", "findings": [cpl_shell()]},
        [deterministic_shell()],
    )

    assert result["findings"] == [cpl_shell()]
    assert result["actionable_findings"] == []
    assert len(result["confirmed_findings"]) == 1
    assert result["decision_verdict"] == "PASS"


def test_model_only_minor_is_preserved_as_advisory_not_action() -> None:
    minor = {
        "category": "tests",
        "severity": "minor",
        "message": "Consider a stronger negative test.",
        "evidence": "assert run_job",
        "evidence_verified": True,
        "path": "tests/test_jobs.py",
        "line_start": 4,
        "line_end": 4,
        "supporting_models": ["model-a"],
    }

    result = reconcile_cpl_findings(
        {"status": "completed", "verdict": "PASS", "findings": [minor]},
        [],
    )

    assert result["actionable_findings"] == []
    assert result["advisory_findings"][0]["classification"] == "advisory"
    assert result["decision_verdict"] == "PASS"


def test_independently_supported_novel_major_remains_actionable() -> None:
    major = {
        "category": "correctness",
        "severity": "major",
        "message": "Returned value violates the documented contract.",
        "evidence": "return None",
        "evidence_verified": True,
        "path": "src/app.py",
        "line_start": 8,
        "line_end": 8,
        "supporting_models": ["model-a", "model-b"],
    }

    result = reconcile_cpl_findings(
        {"status": "completed", "verdict": "NEEDS WORK", "findings": [major]},
        [],
    )

    assert result["actionable_findings"][0]["classification"] == "novel_actionable"
    assert result["decision_verdict"] == "NEEDS WORK"


def test_benchmark_uses_noise_governed_cpl_surface() -> None:
    packet = {
        "repository_review": {"blocking_findings": [], "major_findings": [], "minor_findings": []},
        "diff_review": {"blocking_findings": [], "major_findings": [], "minor_findings": []},
        "capability_review": {"findings": [deterministic_shell()]},
        "cpl_review": {
            "findings": [cpl_shell()],
            "actionable_findings": [],
        },
    }

    predictions, valid_count = extract_predictions(packet)

    assert len(predictions) == 1
    assert valid_count == 1
    assert predictions[0]["source"] == "capability"


def test_effective_pass_recomputes_verdict_after_rejection() -> None:
    finding = cpl_shell()
    passes = [
        {
            "verdict": "BLOCK",
            "findings": [finding],
            "council_resolution": {
                "status": "answered",
                "disposition": "rejected",
                "target_finding": dict(finding),
            },
        }
    ]

    effective = _effective_passes(passes)

    assert effective[0]["findings"] == []
    assert effective[0]["verdict"] == "PASS"


def test_model_route_failover_uses_next_council_member(monkeypatch: pytest.MonkeyPatch) -> None:
    route = LLMRoute(
        provider="cloudflare",
        base_url="https://example.invalid/v1",
        model="model-a",
        protocol="chat_completions",
        discovered_models=("model-a", "model-b"),
    )
    attempts: list[str] = []

    def fake_invoke(candidate: LLMRoute, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        attempts.append(candidate.model)
        if candidate.model == "model-a":
            raise LLMProviderError("model-a failed")
        return {"verdict": "PASS", "findings": []}

    monkeypatch.setattr(llm_review, "invoke_json", fake_invoke)

    payload, used_route, failed_models = llm_review._invoke_json_with_failover(
        route,
        system_prompt="system",
        user_prompt="user",
    )

    assert payload["verdict"] == "PASS"
    assert used_route.model == "model-b"
    assert failed_models == ["model-a"]
    assert attempts == ["model-a", "model-b"]


def test_live_authorization_wording_confirms_existing_authorization_gap() -> None:
    deterministic = {
        "category": "security_taint",
        "severity": "major",
        "message": "Privileged route lacks a visible authorization guard.",
        "evidence": "An admin route was detected without an authorization guard.",
        "path": "src/admin_api.py",
        "line_start": 4,
        "line_end": 4,
        "root_cause": "authorization-gap",
    }
    candidates = [
        {
            "category": "security",
            "severity": "major",
            "message": "Privileged route lacks a visible authorization guard",
            "evidence": "app.delete('/admin/users/:id', delete_user)",
            "evidence_verified": True,
            "path": "src/admin_api.py",
            "line_start": 4,
            "line_end": 4,
            "supporting_models": ["model-a"],
        },
        {
            "category": "security_taint",
            "severity": "major",
            "message": "Privileged admin route defined without any authentication or authorization guard.",
            "evidence": "app.delete('/admin/users/:id', delete_user)",
            "evidence_verified": True,
            "path": "src/admin_api.py",
            "line_start": 4,
            "line_end": 4,
            "supporting_models": ["model-b"],
        },
    ]

    result = reconcile_cpl_findings(
        {"status": "completed", "verdict": "NEEDS WORK", "findings": candidates},
        [deterministic],
    )

    assert len(result["confirmed_findings"]) == 2
    assert result["actionable_findings"] == []
    assert result["unconfirmed_findings"] == []
    assert result["decision_verdict"] == "PASS"


def test_live_sql_interpolation_wording_confirms_existing_unsafe_data_flow() -> None:
    deterministic = {
        "category": "data_flow",
        "severity": "major",
        "message": "User-controlled input appears near a risky sink.",
        "evidence": "Input and sink patterns were both detected in the changed file.",
        "path": "src/api.py",
        "line_start": 3,
        "line_end": 3,
        "root_cause": "unsafe-data-flow",
    }
    candidate = {
        "category": "correctness",
        "severity": "major",
        "message": "User-controlled input directly interpolated into SQL query without parameterization",
        "evidence": 'return db.query(f"SELECT * FROM users WHERE id = {user_id}")',
        "evidence_verified": True,
        "path": "src/api.py",
        "line_start": 3,
        "line_end": 3,
        "supporting_models": ["model-b"],
    }

    result = reconcile_cpl_findings(
        {"status": "completed", "verdict": "NEEDS WORK", "findings": [candidate]},
        [deterministic],
    )

    assert len(result["confirmed_findings"]) == 1
    assert result["actionable_findings"] == []
    assert result["unconfirmed_findings"] == []
    assert result["decision_verdict"] == "PASS"


def test_same_family_findings_remain_separate_when_far_apart() -> None:
    left = {**cpl_shell(), "line_start": 5, "line_end": 5}
    right = {**deterministic_shell(), "line_start": 50, "line_end": 50}

    assert findings_overlap(left, right) is False


def test_supporting_model_normalization_drops_null_values() -> None:
    major = {
        "category": "correctness",
        "severity": "major",
        "message": "Returned value violates the documented contract.",
        "evidence": "return None",
        "evidence_verified": True,
        "path": "src/app.py",
        "line_start": 8,
        "line_end": 8,
        "supporting_models": [None, "model-a", "model-b"],
    }

    result = reconcile_cpl_findings(
        {"status": "completed", "verdict": "NEEDS WORK", "findings": [major]},
        [],
    )

    assert result["actionable_findings"][0]["supporting_models"] == ["model-a", "model-b"]


def test_all_model_failures_report_only_safe_failure_categories(monkeypatch: pytest.MonkeyPatch) -> None:
    route = LLMRoute(
        provider="cloudflare",
        base_url="https://example.invalid/v1",
        model="model-a",
        protocol="chat_completions",
        discovered_models=("model-a", "model-b"),
    )

    def fail(candidate: LLMRoute, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        raise LLMProviderError(
            "Cpl model endpoint returned HTTP 429: private upstream response text"
        )

    monkeypatch.setattr(llm_review, "invoke_json", fail)

    with pytest.raises(LLMProviderError) as captured:
        llm_review._invoke_json_with_failover(
            route,
            system_prompt="system",
            user_prompt="user",
        )

    message = str(captured.value)
    assert "http_429=2" in message
    assert "private upstream response text" not in message


def test_final_decision_uses_noise_governed_cpl_verdict() -> None:
    verdict = _decide(
        {"verdict": "PASS"},
        {"passed": True, "blockers": []},
        {"verdict": {"verdict": "PASS"}},
        {"verdict": "PASS", "ranked_findings": []},
        {"confidence_after_challenge": 0.9},
        {
            "status": "completed",
            "policy": "required",
            "verdict": "NEEDS WORK",
            "decision_verdict": "PASS",
            "confidence": 0.8,
            "findings": [],
            "actionable_findings": [],
            "council": {"mode": "elastic_multi_model", "complete": True},
        },
        {"consensus": "PASS"},
    )

    assert verdict.verdict == "APPROVE"
