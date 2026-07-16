from __future__ import annotations

from pathlib import Path

import pytest

from main_review import llm_provider
from main_review.cloudflare_usage import (
    CloudflareBudgetExceeded,
    CloudflareQuotaBlocked,
    CloudflareUsageGovernor,
    cloudflare_usage_status,
    estimate_neurons,
)


def _route() -> llm_provider.LLMRoute:
    return llm_provider.LLMRoute(
        provider="cloudflare-workers-ai",
        base_url="https://api.cloudflare.com/client/v4/accounts/0123456789abcdef0123456789abcdef/ai/v1",
        model="@cf/qwen/qwen3-30b-a3b-fp8",
        protocol="chat_completions",
        api_key="secret",
        max_output_tokens=900,
    )


def _configure(monkeypatch, path: Path, *, limit: int = 10_000, reserve: int = 0) -> None:
    monkeypatch.setenv("SERGEANT_CLOUDFLARE_USAGE_STATE", str(path))
    monkeypatch.setenv("SERGEANT_CLOUDFLARE_DAILY_BUDGET_NEURONS", str(limit))
    monkeypatch.setenv("SERGEANT_CLOUDFLARE_SAFETY_RESERVE_NEURONS", str(reserve))
    monkeypatch.setenv("SERGEANT_CLOUDFLARE_USAGE_GOVERNOR", "true")


def test_model_profiles_produce_cost_sensitive_reservations() -> None:
    granite = estimate_neurons(
        "@cf/ibm-granite/granite-4.0-h-micro",
        input_chars=6000,
        max_output_tokens=700,
    )
    qwen = estimate_neurons(
        "@cf/qwen/qwen3-30b-a3b-fp8",
        input_chars=6000,
        max_output_tokens=900,
    )
    coder = estimate_neurons(
        "@cf/qwen/qwen2.5-coder-32b-instruct",
        input_chars=6000,
        max_output_tokens=1800,
    )

    assert 0 < granite < qwen < coder


def test_reservation_persists_and_blocks_before_daily_budget(monkeypatch, tmp_path) -> None:
    state_path = tmp_path / "usage.json"
    _configure(monkeypatch, state_path, limit=40, reserve=0)
    governor = CloudflareUsageGovernor(state_path)

    first = governor.reserve(
        model="@cf/qwen/qwen3-30b-a3b-fp8",
        input_chars=100,
        max_output_tokens=900,
        stage="test",
    )
    assert first["estimated_neurons"] > 0
    assert state_path.is_file()

    with pytest.raises(CloudflareBudgetExceeded, match="blocked before inference"):
        governor.reserve(
            model="@cf/qwen/qwen3-30b-a3b-fp8",
            input_chars=100,
            max_output_tokens=900,
            stage="test-two",
        )

    status = governor.status()
    assert status["request_count"] == 1
    assert status["reserved_neurons"] == first["estimated_neurons"]


def test_quota_block_is_persistent(monkeypatch, tmp_path) -> None:
    state_path = tmp_path / "usage.json"
    _configure(monkeypatch, state_path)
    governor = CloudflareUsageGovernor(state_path)
    blocked = governor.mark_quota_blocked()

    assert blocked["quota_blocked"] is True
    with pytest.raises(CloudflareQuotaBlocked, match="quota circuit is open"):
        CloudflareUsageGovernor(state_path).reserve(
            model="@cf/qwen/qwen3-30b-a3b-fp8",
            input_chars=100,
            max_output_tokens=100,
            stage="after-block",
        )


def test_http_429_opens_circuit_and_prevents_retry_cascade(monkeypatch, tmp_path) -> None:
    state_path = tmp_path / "usage.json"
    _configure(monkeypatch, state_path)
    calls: list[str] = []

    def quota_failure(request, timeout):
        calls.append(request.full_url)
        raise llm_provider.LLMProviderError(
            'Cpl model endpoint returned HTTP 429: {"errors":[{"code":4006,"message":"daily free allocation"}]}'
        )

    monkeypatch.setattr(llm_provider, "_load_json_response", quota_failure)

    with pytest.raises(llm_provider.LLMProviderError, match="quota circuit opened"):
        llm_provider.invoke_json(_route(), system_prompt="system", user_prompt="user")

    assert len(calls) == 1
    assert cloudflare_usage_status()["quota_blocked"] is True

    with pytest.raises(llm_provider.LLMProviderError, match="quota circuit is open"):
        llm_provider.invoke_json(_route(), system_prompt="system", user_prompt="user")

    assert len(calls) == 1


def test_budget_guard_prevents_network_request(monkeypatch, tmp_path) -> None:
    state_path = tmp_path / "usage.json"
    _configure(monkeypatch, state_path, limit=1, reserve=0)
    calls: list[str] = []

    def unexpected_request(request, timeout):
        calls.append(request.full_url)
        return {"choices": [{"message": {"content": '{"status":"ready"}'}}]}

    monkeypatch.setattr(llm_provider, "_load_json_response", unexpected_request)

    with pytest.raises(llm_provider.LLMProviderError, match="blocked before inference"):
        llm_provider.invoke_json(_route(), system_prompt="system", user_prompt="user")

    assert calls == []
