from __future__ import annotations

from main_review.cloudflare_models import (
    CLOUDFLARE_FREE_BALANCED_MODELS,
    cloudflare_base_url,
    configured_model_roster,
    parse_model_list,
)
from main_review.llm_provider import LLMSettings, discover_route


def test_parse_model_list_preserves_order_and_removes_duplicates() -> None:
    assert parse_model_list("model-a, model-b\nmodel-a") == ("model-a", "model-b")


def test_cloudflare_base_url_rejects_unsafe_account_id() -> None:
    assert cloudflare_base_url("account-123") == (
        "https://api.cloudflare.com/client/v4/accounts/account-123/ai/v1"
    )
    assert cloudflare_base_url("bad/account") == ""


def test_cloudflare_settings_use_scoped_environment_without_exposing_secret(monkeypatch) -> None:
    monkeypatch.setenv("SERGEANT_CPL_PROVIDER", "cloudflare")
    monkeypatch.setenv("SERGEANT_CLOUDFLARE_ACCOUNT_ID", "1234567890abcdef")
    monkeypatch.setenv("SERGEANT_CLOUDFLARE_API_TOKEN", "top-secret-token")

    settings = LLMSettings.from_environment()
    public = settings.public_dict()

    assert settings.base_url == (
        "https://api.cloudflare.com/client/v4/accounts/1234567890abcdef/ai/v1"
    )
    assert settings.api_key == "top-secret-token"
    assert settings.model == CLOUDFLARE_FREE_BALANCED_MODELS[0]
    assert settings.max_output_tokens == 1800
    assert public["base_url"] == "https://api.cloudflare.com/client/v4/accounts/***/ai/v1"
    assert public["configured_models"] == list(CLOUDFLARE_FREE_BALANCED_MODELS)
    assert "top-secret-token" not in str(public)
    assert "1234567890abcdef" not in str(public)


def test_cloudflare_credentials_auto_select_provider(monkeypatch) -> None:
    monkeypatch.setenv("SERGEANT_CPL_ENABLED", "true")
    monkeypatch.delenv("SERGEANT_CPL_PROVIDER", raising=False)
    monkeypatch.delenv("SERGEANT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("SERGEANT_CPL_BASE_URL", raising=False)
    monkeypatch.delenv("SERGEANT_LLM_BASE_URL", raising=False)
    monkeypatch.setenv("SERGEANT_CLOUDFLARE_ACCOUNT_ID", "1234567890abcdef")
    monkeypatch.setenv("SERGEANT_CLOUDFLARE_API_TOKEN", "token")

    settings = LLMSettings.from_environment()

    assert settings.enabled is True
    assert settings.provider == "cloudflare"
    assert settings.model == CLOUDFLARE_FREE_BALANCED_MODELS[0]


def test_cloudflare_default_roster_is_balanced(monkeypatch) -> None:
    monkeypatch.delenv("SERGEANT_CPL_MODELS", raising=False)
    monkeypatch.delenv("SERGEANT_CPL_MODEL_PRESET", raising=False)

    assert configured_model_roster("cloudflare") == CLOUDFLARE_FREE_BALANCED_MODELS
    assert configured_model_roster("configured") == ()


def test_explicit_roster_wins_over_cloudflare_preset(monkeypatch) -> None:
    monkeypatch.setenv("SERGEANT_CPL_MODELS", "model-one,model-two")
    monkeypatch.setenv("SERGEANT_CPL_MODEL_PRESET", "cloudflare-free-strong")

    assert configured_model_roster("cloudflare") == ("model-one", "model-two")


def test_discover_route_uses_cloudflare_roster_without_model_listing(monkeypatch) -> None:
    monkeypatch.setenv("SERGEANT_CPL_ENABLED", "true")
    monkeypatch.setenv("SERGEANT_CPL_PROVIDER", "cloudflare")
    monkeypatch.setenv("SERGEANT_CLOUDFLARE_ACCOUNT_ID", "1234567890abcdef")
    monkeypatch.setenv("SERGEANT_CLOUDFLARE_API_TOKEN", "token")
    monkeypatch.setattr(
        "main_review.llm_provider.list_models",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not list models")),
    )

    route = discover_route()

    assert route is not None
    assert route.provider == "cloudflare"
    assert route.model == CLOUDFLARE_FREE_BALANCED_MODELS[0]
    assert route.discovered_models == CLOUDFLARE_FREE_BALANCED_MODELS
    assert route.protocol == "chat_completions"
    assert route.public_dict()["base_url"].endswith("/accounts/***/ai/v1")


def test_cloudflare_alias_is_normalized(monkeypatch) -> None:
    monkeypatch.setenv("SERGEANT_CPL_PROVIDER", "workers-ai")
    monkeypatch.setenv("SERGEANT_CLOUDFLARE_ACCOUNT_ID", "1234567890abcdef")
    monkeypatch.setenv("SERGEANT_CLOUDFLARE_API_TOKEN", "token")

    settings = LLMSettings.from_environment()

    assert settings.provider == "cloudflare"
