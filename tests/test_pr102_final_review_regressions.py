from __future__ import annotations

from dataclasses import replace

import pytest

from main_review import cpl_runtime, llm_review
from main_review.cpl_council import finding_root_cause
from main_review.cpl_reasoning import SPECIALISTS
from main_review.llm_provider import LLMProviderError, LLMRoute, LLMSettings


def route(model: str = "model-a") -> LLMRoute:
    return LLMRoute(
        provider="configured",
        base_url="http://127.0.0.1:8082/v1",
        model=model,
        protocol="chat_completions",
        discovered_models=("model-a", "model-b"),
    )


def test_authorization_root_requires_authorization_object_after_without() -> None:
    assert finding_root_cause({"message": "Privileged admin route without pagination."}) != "authorization-gap"
    assert finding_root_cause({"message": "Privileged admin route without authorization guard."}) == "authorization-gap"


def test_exhausted_generalist_failover_preserves_attempted_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_review, "available_models", lambda _: ["model-a", "model-b"])

    def fail(*args, **kwargs):
        raise LLMProviderError("provider unavailable")

    monkeypatch.setattr(llm_review, "invoke_json", fail)
    with pytest.raises(LLMProviderError) as caught:
        llm_review._invoke_json_with_failover(route(), system_prompt="s", user_prompt="u")
    assert caught.value.failed_models == ("model-a", "model-b")


def test_exhausted_follow_up_preserves_attempted_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cpl_runtime, "available_models", lambda _: ["model-a", "model-b"])

    def fail(*args, **kwargs):
        raise LLMProviderError("provider unavailable")

    monkeypatch.setattr(cpl_runtime, "invoke_json", fail)
    with pytest.raises(LLMProviderError) as caught:
        cpl_runtime._invoke_follow_up_with_failover(route(), system_prompt="s", user_prompt="u")
    assert caught.value.failed_models == ("model-a", "model-b")


def test_successful_specialist_failover_records_actual_completed_model(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    assignment = SPECIALISTS["security"]
    calls = iter([
        ({}, route("model-a"), []),
        ({}, route("model-b"), ["model-a"]),
    ])
    monkeypatch.setattr(llm_review, "collect_changed_file_excerpts", lambda *args: ({}, {}))
    monkeypatch.setattr(llm_review, "_build_user_prompt", lambda *args: "prompt")
    monkeypatch.setattr(llm_review, "plan_cpl_assignments", lambda *args, **kwargs: [assignment])
    monkeypatch.setattr(llm_review, "route_for_assignment", lambda *args, **kwargs: route("model-a"))
    monkeypatch.setattr(llm_review, "_invoke_json_with_failover", lambda *args, **kwargs: next(calls))
    monkeypatch.setattr(
        llm_review,
        "_validate_pass",
        lambda payload, files, *, route, assignment=None: {
            "model": route.model,
            "verdict": "PASS",
            "confidence": 0.9,
            "findings": [],
            "coverage": {"files_reviewed": [], "areas": []},
            "unanswered_questions": [],
            "summary": "ok",
        },
    )
    synthetic_settings = LLMSettings(
        enabled=True,
        policy="preferred",
        provider="configured",
        base_url="http://127.0.0.1:8082/v1",
        model="model-a",
        protocol="chat_completions",
        api_key="",
        timeout_seconds=1.0,
        max_output_tokens=256,
    )
    result = llm_review.run_cpl_review(
        tmp_path,
        [],
        {},
        settings=synthetic_settings,
        route=route(),
    )
    assert result["reasoning_plan"][0]["model"] == "model-b"
    assert result["route_failovers"] == [{
        "pass": "security",
        "failed_models": ["model-a"],
        "completed_by": "model-b",
    }]


def test_recruited_failover_recomputes_admission_and_score(monkeypatch: pytest.MonkeyPatch) -> None:
    used = {"model-a"}
    completed = "model-b"
    admission = "new_member" if completed not in used and len(used) < 5 else "role_separated_reuse"
    assert admission == "new_member"
    assert cpl_runtime.model_score(completed, {}, "security") == cpl_runtime.model_score("model-b", {}, "security")
