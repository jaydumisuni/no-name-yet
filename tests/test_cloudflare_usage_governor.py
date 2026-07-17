from __future__ import annotations

import json
import multiprocessing
import os
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


def _reserve_in_process(state_path: str, start_event, result_queue) -> None:
    os.environ["SERGEANT_CLOUDFLARE_USAGE_STATE"] = state_path
    os.environ["SERGEANT_CLOUDFLARE_DAILY_BUDGET_NEURONS"] = "10000"
    os.environ["SERGEANT_CLOUDFLARE_SAFETY_RESERVE_NEURONS"] = "0"
    os.environ["SERGEANT_CLOUDFLARE_USAGE_GOVERNOR"] = "true"
    start_event.wait(timeout=10)
    try:
        result = CloudflareUsageGovernor(Path(state_path)).reserve(
            model="@cf/ibm-granite/granite-4.0-h-micro",
            input_chars=100,
            max_output_tokens=100,
            stage=f"worker-{os.getpid()}",
        )
        result_queue.put(("ok", result["estimated_neurons"]))
    except Exception as error:  # pragma: no cover - returned to parent for assertion
        result_queue.put(("error", repr(error)))


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


def test_concurrent_processes_preserve_both_reservations(tmp_path) -> None:
    state_path = tmp_path / "usage.json"
    context = multiprocessing.get_context("spawn")
    start_event = context.Event()
    result_queue = context.Queue()
    processes = [
        context.Process(
            target=_reserve_in_process,
            args=(str(state_path), start_event, result_queue),
        )
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    start_event.set()
    results = [result_queue.get(timeout=20) for _ in processes]
    for process in processes:
        process.join(timeout=20)
        assert process.exitcode == 0

    assert [status for status, _ in results] == ["ok", "ok"]
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["request_count"] == 2
    assert len(payload["reservations"]) == 2
    assert not list(tmp_path.glob(".usage.json.*.tmp"))


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


def test_allocation_429_opens_circuit_and_prevents_retry_cascade(monkeypatch, tmp_path) -> None:
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


def test_generic_429_does_not_open_daily_quota_circuit(monkeypatch, tmp_path) -> None:
    state_path = tmp_path / "usage.json"
    _configure(monkeypatch, state_path)
    calls: list[str] = []

    def throttle_failure(request, timeout):
        calls.append(request.full_url)
        raise llm_provider.LLMProviderError(
            'Cpl model endpoint returned HTTP 429: {"message":"temporarily rate limited"}'
        )

    monkeypatch.setattr(llm_provider, "_load_json_response", throttle_failure)

    with pytest.raises(llm_provider.LLMProviderError, match="HTTP 429"):
        llm_provider.invoke_json(_route(), system_prompt="system", user_prompt="user")

    assert len(calls) == 1
    assert cloudflare_usage_status()["quota_blocked"] is False


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
