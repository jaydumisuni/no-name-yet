from __future__ import annotations

from main_review import cloudflare_cli
from main_review.cloudflare_gateway import CloudflareGatewaySettings, DEFAULT_MODELS
from main_review.cloudflare_models import (
    CLOUDFLARE_FREE_BALANCED_MODELS,
    cloudflare_base_url,
    configured_model_roster,
    public_base_url,
)


def test_direct_and_gateway_routes_share_balanced_default(monkeypatch) -> None:
    for name in (
        "SERGEANT_CLOUDFLARE_MODELS",
        "SERGEANT_CPL_MODELS",
        "SERGEANT_CPL_MODEL_PRESET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SERGEANT_CLOUDFLARE_ACCOUNT_ID", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("SERGEANT_CLOUDFLARE_API_TOKEN", "token")

    settings = CloudflareGatewaySettings.from_environment()

    assert DEFAULT_MODELS == CLOUDFLARE_FREE_BALANCED_MODELS
    assert settings.models == CLOUDFLARE_FREE_BALANCED_MODELS
    assert configured_model_roster("cloudflare") == settings.models


def test_cloudflare_specific_roster_wins_over_generic_roster(monkeypatch) -> None:
    monkeypatch.setenv("SERGEANT_CLOUDFLARE_MODELS", "model-a,model-b")
    monkeypatch.setenv("SERGEANT_CPL_MODELS", "model-c,model-d")

    assert configured_model_roster("cloudflare") == ("model-a", "model-b")


def test_cloudflare_account_id_validation_is_shared() -> None:
    valid = "0123456789abcdef0123456789abcdef"

    assert cloudflare_base_url(valid).endswith(f"/accounts/{valid}/ai/v1")
    assert cloudflare_base_url("account-123") == ""


def test_all_cloudflare_provider_aliases_mask_account_id() -> None:
    account_id = "0123456789abcdef0123456789abcdef"
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1"

    for provider in ("cloudflare", "cloudflare-workers-ai", "workers-ai", "cf"):
        masked = public_base_url(provider, url)
        assert account_id not in masked
        assert "/accounts/***/" in masked


def test_live_proof_routes_use_bounded_output_tokens() -> None:
    settings = CloudflareGatewaySettings(
        account_id="0123456789abcdef0123456789abcdef",
        api_token="secret-token",
        models=CLOUDFLARE_FREE_BALANCED_MODELS,
    )

    council = cloudflare_cli.cloudflare_route(settings)
    model_probe = cloudflare_cli.cloudflare_route(
        settings,
        max_output_tokens=cloudflare_cli.MODEL_PROOF_MAX_OUTPUT_TOKENS,
    )

    assert council.max_output_tokens == cloudflare_cli.COUNCIL_PROOF_MAX_OUTPUT_TOKENS
    assert model_probe.max_output_tokens == cloudflare_cli.MODEL_PROOF_MAX_OUTPUT_TOKENS
    assert model_probe.max_output_tokens < council.max_output_tokens
