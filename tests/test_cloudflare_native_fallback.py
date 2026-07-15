from __future__ import annotations

from pathlib import Path

import pytest

from main_review import llm_provider
from main_review.cloudflare_models import model_proof_output_tokens


def _route(provider: str = "cloudflare-workers-ai") -> llm_provider.LLMRoute:
    return llm_provider.LLMRoute(
        provider=provider,
        base_url="https://api.cloudflare.com/client/v4/accounts/0123456789abcdef0123456789abcdef/ai/v1",
        model="@cf/qwen/qwen3-30b-a3b-fp8",
        protocol="chat_completions",
        api_key="secret",
        max_output_tokens=900,
    )


def test_extracts_cloudflare_native_response_envelopes() -> None:
    assert llm_provider._extract_text({"response": '{"ok": true}'}, "chat_completions") == '{"ok": true}'
    assert llm_provider._extract_text(
        {"result": {"response": '{"ok": true}'}}, "chat_completions"
    ) == '{"ok": true}'


def test_cloudflare_falls_back_to_native_route(monkeypatch) -> None:
    responses = iter(
        [
            {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]},
            {"result": {"response": '{"status": "ready"}'}},
        ]
    )
    urls: list[str] = []

    def fake_load(request, timeout):
        urls.append(request.full_url)
        return next(responses)

    monkeypatch.setattr(llm_provider, "_load_json_response", fake_load)
    result = llm_provider.invoke_json(_route(), system_prompt="system", user_prompt="user")

    assert result == {"status": "ready"}
    assert urls[0].endswith("/ai/v1/chat/completions")
    assert urls[1].endswith("/ai/run/@cf/qwen/qwen3-30b-a3b-fp8")


def test_generic_provider_does_not_use_cloudflare_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_provider,
        "_load_json_response",
        lambda request, timeout: {"choices": [{"message": {"content": ""}}]},
    )
    with pytest.raises(llm_provider.LLMProviderError, match="Response shape"):
        llm_provider.invoke_json(_route("configured"), system_prompt="system", user_prompt="user")


def test_reasoning_models_receive_larger_proof_budget() -> None:
    assert model_proof_output_tokens("@cf/qwen/qwen3-30b-a3b-fp8") == 900
    assert model_proof_output_tokens("@cf/zai-org/glm-4.7-flash") == 900
    assert model_proof_output_tokens("@cf/qwen/qwen2.5-coder-32b-instruct") == 384


def test_dual_route_error_does_not_echo_upstream_body(monkeypatch) -> None:
    responses = iter(
        [
            {"choices": [{"message": {"content": ""}}]},
            llm_provider.LLMProviderError("upstream body: private provider detail"),
        ]
    )

    def fake_load(request, timeout):
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(llm_provider, "_load_json_response", fake_load)
    with pytest.raises(llm_provider.LLMProviderError) as captured:
        llm_provider.invoke_json(_route(), system_prompt="system", user_prompt="user")

    message = str(captured.value)
    assert "private provider detail" not in message
    assert message == (
        "Cloudflare OpenAI-compatible and native model routes both failed without a parseable JSON response."
    )


def test_fallback_helpers_are_defined_once() -> None:
    provider_source = Path(llm_provider.__file__).read_text(encoding="utf-8")
    from main_review import cloudflare_cli, cloudflare_models

    model_source = Path(cloudflare_models.__file__).read_text(encoding="utf-8")
    cli_source = Path(cloudflare_cli.__file__).read_text(encoding="utf-8")

    assert provider_source.count("def _response_shape(") == 1
    assert provider_source.count("def _cloudflare_native_endpoint(") == 1
    assert model_source.count("def model_proof_output_tokens(") == 1
    assert model_source.count("CLOUDFLARE_REASONING_MODELS = {") == 1
    assert cli_source.count("from .cloudflare_models import (") == 1
