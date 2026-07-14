from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from main_review import cloudflare_cli
from main_review.cloudflare_gateway import (
    CloudflareGatewayError,
    CloudflareGatewaySettings,
    build_server,
    is_loopback_host,
)


def settings(**overrides: object) -> CloudflareGatewaySettings:
    values = {
        "account_id": "0123456789abcdef0123456789abcdef",
        "api_token": "secret-token",
        "models": (
            "@cf/zai-org/glm-4.7-flash",
            "@cf/openai/gpt-oss-120b",
        ),
        "host": "127.0.0.1",
        "port": 0,
        "timeout_seconds": 10.0,
        "max_request_bytes": 100_000,
        "allow_network": False,
    }
    values.update(overrides)
    return CloudflareGatewaySettings(**values)  # type: ignore[arg-type]


def test_public_settings_never_expose_credentials() -> None:
    payload = settings().public_dict()

    assert payload["configured"] is True
    assert payload["api_token_present"] is True
    assert "secret-token" not in json.dumps(payload)
    assert "api_token" not in payload


def test_account_id_must_be_32_character_hexadecimal() -> None:
    with pytest.raises(CloudflareGatewayError, match="32-character hexadecimal"):
        settings(account_id="account-123").validate()


def test_loopback_is_required_by_default() -> None:
    assert is_loopback_host("127.0.0.1") is True
    assert is_loopback_host("localhost") is True

    with pytest.raises(CloudflareGatewayError, match="loopback"):
        settings(host="0.0.0.0").validate()

    settings(host="0.0.0.0", allow_network=True).validate()


def test_model_roster_is_required_and_cloudflare_scoped() -> None:
    with pytest.raises(CloudflareGatewayError, match="At least one"):
        settings(models=()).validate()

    with pytest.raises(CloudflareGatewayError, match="@cf/"):
        settings(models=("not-cloudflare",)).validate()


def test_gateway_exposes_openai_compatible_model_list() -> None:
    configured = settings()
    server = build_server(configured)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=3) as response:
            payload = json.loads(response.read())
        assert [item["id"] for item in payload["data"]] == list(configured.models)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_gateway_rejects_models_outside_roster_without_upstream_call() -> None:
    configured = settings()
    server = build_server(configured)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            data=json.dumps({"model": "@cf/unknown/model", "messages": [{"role": "user", "content": "hello"}]}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(request, timeout=3)
        assert raised.value.code == 502
        assert "not in the configured Cloudflare roster" in raised.value.read().decode()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_cloudflare_route_exposes_full_model_roster() -> None:
    route = cloudflare_cli.cloudflare_route(settings())

    assert route.provider == "cloudflare-workers-ai"
    assert route.protocol == "chat_completions"
    assert route.model == "@cf/zai-org/glm-4.7-flash"
    assert route.discovered_models == settings().models
    assert route.base_url.endswith("/ai/v1")


def test_model_proof_calls_every_configured_model(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    def fake_invoke(route: object, *, system_prompt: str, user_prompt: str) -> dict[str, object]:
        model = getattr(route, "model")
        called.append(model)
        return {"status": "ready", "model": model, "capabilities": ["structured_json", "reasoning"]}

    monkeypatch.setattr(cloudflare_cli, "invoke_json", fake_invoke)

    result = cloudflare_cli.test_models(settings())

    assert result["all_passed"] is True
    assert result["passed_count"] == 2
    assert called == list(settings().models)


def test_council_proof_requires_real_model_independence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def add(left, right):\n    return left + right\n", encoding="utf-8")

    def fake_review(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "status": "completed",
            "verdict": "PASS",
            "passes": [
                {"model": "@cf/zai-org/glm-4.7-flash"},
                {"model": "@cf/openai/gpt-oss-120b"},
            ],
            "errors": [],
            "council": {
                "true_model_independence": True,
                "complete": True,
                "final_gaps": [],
            },
        }

    monkeypatch.setattr(cloudflare_cli, "run_cpl_review", fake_review)

    result = cloudflare_cli.run_council_proof(
        settings(),
        root=tmp_path,
        changed_files=["sample.py"],
    )

    assert result["passed"] is True
    assert result["true_model_independence"] is True
    assert result["distinct_models"] == [
        "@cf/openai/gpt-oss-120b",
        "@cf/zai-org/glm-4.7-flash",
    ]


def test_council_proof_rejects_single_model_roster(tmp_path: Path) -> None:
    with pytest.raises(CloudflareGatewayError, match="at least two"):
        cloudflare_cli.run_council_proof(
            settings(models=("@cf/zai-org/glm-4.7-flash",)),
            root=tmp_path,
            changed_files=["sample.py"],
        )
