"""Provider routing beneath Sergeant's Cpl reasoning officer.

Cpl owns provider-independent reasoning policy while this module supplies stable
HTTP transports. It can use a local Cpl gateway, Ollama, LM Studio, Cloudflare
Workers AI, or any explicitly configured OpenAI-compatible service without
provider SDKs.

Automatic discovery probes loopback endpoints only. Remote code transmission
requires an explicit base URL or an explicitly selected provider connector.
"""
from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Literal

from .cloudflare_models import (
    CLOUDFLARE_PROVIDER,
    cloudflare_environment,
    configured_model_roster,
    public_base_url,
)

LLMProtocol = Literal["responses", "chat_completions"]
LLMPolicy = Literal["preferred", "required", "disabled"]

DEFAULT_CPL_BASE_URL = "http://127.0.0.1:8082/v1"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_LM_STUDIO_BASE_URL = "http://127.0.0.1:1234/v1"

# Order matters. Cpl first prefers explicitly proven deep coding routes, then
# efficient Cloudflare council members, then other coding/agentic routes.
PREFERRED_MODEL_NEEDLES = (
    "glm-5.2",
    "qwen3-coder-next",
    "kimi-k2.7-code",
    "kimi-k2.6",
    "kimi-k2.5",
    "glm-5.1",
    "qwen3-coder",
    "kimi-k2",
    "qwen3-30b-a3b",
    "glm-4.7-flash",
    "gpt-oss-20b",
    "qwen2.5-coder-32b",
    "gpt-oss-120b",
    "granite-4.0-h-micro",
)


class LLMProviderError(RuntimeError):
    """Raised when a configured Cpl model endpoint cannot satisfy a request."""


@dataclass(frozen=True)
class LLMSettings:
    enabled: bool
    policy: LLMPolicy
    provider: str
    base_url: str
    model: str
    protocol: str
    api_key: str
    timeout_seconds: float
    max_output_tokens: int

    @classmethod
    def from_environment(cls) -> "LLMSettings":
        policy_raw = _env("SERGEANT_CPL_POLICY", "SERGEANT_LLM_POLICY", "preferred").strip().lower()
        policy: LLMPolicy = (
            policy_raw if policy_raw in {"preferred", "required", "disabled"} else "preferred"
        )  # type: ignore[assignment]
        enabled_raw = _env("SERGEANT_CPL_ENABLED", "SERGEANT_LLM_ENABLED", "auto").strip().lower()
        enabled = policy != "disabled" and enabled_raw not in {"0", "false", "no", "off", "disabled"}
        provider = _normalize_provider(_env("SERGEANT_CPL_PROVIDER", "SERGEANT_LLM_PROVIDER", "auto"))
        base_url = _env("SERGEANT_CPL_BASE_URL", "SERGEANT_LLM_BASE_URL", "").strip()
        api_key = _env("SERGEANT_CPL_API_KEY", "SERGEANT_LLM_API_KEY", "").strip()
        model = _env("SERGEANT_CPL_MODEL", "SERGEANT_LLM_MODEL", "").strip()

        cloudflare_base, cloudflare_token = cloudflare_environment()
        # Make Cloudflare the easiest hosted route: valid Cloudflare credentials
        # are sufficient when no explicit generic provider/base URL was chosen.
        if provider == "auto" and not base_url and cloudflare_base and cloudflare_token:
            provider = CLOUDFLARE_PROVIDER

        if provider == CLOUDFLARE_PROVIDER:
            base_url = base_url or cloudflare_base
            api_key = api_key or cloudflare_token
            roster = configured_model_roster(provider)
            model = model or (roster[0] if roster else "")

        output_default = 1800 if provider == CLOUDFLARE_PROVIDER else 5000
        return cls(
            enabled=enabled,
            policy=policy,
            provider=provider,
            base_url=base_url,
            model=model,
            protocol=_env("SERGEANT_CPL_PROTOCOL", "SERGEANT_LLM_PROTOCOL", "auto").strip().lower() or "auto",
            api_key=api_key,
            timeout_seconds=_float_env_pair(
                "SERGEANT_CPL_TIMEOUT_SECONDS",
                "SERGEANT_LLM_TIMEOUT_SECONDS",
                90.0,
                minimum=1.0,
                maximum=900.0,
            ),
            max_output_tokens=_int_env_pair(
                "SERGEANT_CPL_MAX_OUTPUT_TOKENS",
                "SERGEANT_LLM_MAX_OUTPUT_TOKENS",
                output_default,
                minimum=256,
                maximum=32000,
            ),
        )

    def public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("api_key", None)
        payload["base_url"] = public_base_url(self.provider, self.base_url)
        payload["configured_models"] = list(configured_model_roster(self.provider))
        payload["officer"] = "Cpl"
        payload["role"] = "Corporal Specialist"
        return payload


@dataclass(frozen=True)
class LLMRoute:
    provider: str
    base_url: str
    model: str
    protocol: LLMProtocol
    api_key: str = ""
    timeout_seconds: float = 90.0
    max_output_tokens: int = 5000
    discovered_models: tuple[str, ...] = ()

    def public_dict(self) -> dict[str, object]:
        return {
            "officer": "Cpl",
            "role": "Corporal Specialist",
            "provider": self.provider,
            "base_url": public_base_url(self.provider, self.base_url),
            "model": self.model,
            "protocol": self.protocol,
            "timeout_seconds": self.timeout_seconds,
            "max_output_tokens": self.max_output_tokens,
            "discovered_models": list(self.discovered_models),
        }


def _env(primary: str, legacy: str, default: str) -> str:
    value = os.getenv(primary)
    if value is not None:
        return value
    return os.getenv(legacy, default)


def _normalize_provider(value: str) -> str:
    provider = value.strip().lower() or "auto"
    if provider == "fcc":
        return "cpl"
    if provider == "openai-compatible":
        return "configured"
    if provider in {"workers-ai", "cloudflare-workers-ai", "cf"}:
        return CLOUDFLARE_PROVIDER
    return provider


def _float_env_pair(
    primary: str,
    legacy: str,
    default: float,
    *,
    minimum: float,
    maximum: float,
) -> float:
    try:
        value = float(_env(primary, legacy, str(default)))
    except ValueError:
        return default
    return min(maximum, max(minimum, value))


def _int_env_pair(
    primary: str,
    legacy: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    try:
        value = int(_env(primary, legacy, str(default)))
    except ValueError:
        return default
    return min(maximum, max(minimum, value))


def _normalize_base_url(value: str) -> str:
    base = value.strip().rstrip("/")
    if base and not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


def _request_headers(api_key: str) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "sergeant-reviewer/cpl-router",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _load_json_response(request: urllib.request.Request, timeout: float) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:1000]
        raise LLMProviderError(f"Cpl model endpoint returned HTTP {error.code}: {detail}") from error
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as error:
        raise LLMProviderError(f"Cpl model endpoint is unavailable: {error}") from error

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        raise LLMProviderError("Cpl model endpoint returned a non-JSON response.") from error
    if not isinstance(payload, dict):
        raise LLMProviderError("Cpl model endpoint returned an unexpected JSON shape.")
    return payload


def list_models(base_url: str, *, api_key: str = "", timeout_seconds: float = 3.0) -> tuple[str, ...]:
    request = urllib.request.Request(
        f"{_normalize_base_url(base_url)}/models",
        headers=_request_headers(api_key),
        method="GET",
    )
    payload = _load_json_response(request, timeout_seconds)
    raw_models = payload.get("data", payload.get("models", []))
    models: list[str] = []
    if isinstance(raw_models, list):
        for item in raw_models:
            if isinstance(item, str):
                models.append(item)
            elif isinstance(item, dict):
                model_id = item.get("id") or item.get("name") or item.get("model")
                if isinstance(model_id, str) and model_id.strip():
                    models.append(model_id.strip())
    return tuple(dict.fromkeys(models))


def select_model(models: tuple[str, ...], configured: str = "") -> str:
    if configured:
        return configured
    lowered = [(model, model.lower()) for model in models]
    for needle in PREFERRED_MODEL_NEEDLES:
        for model, normalized in lowered:
            if needle in normalized:
                return model
    return models[0] if models else ""


def _protocol_for(provider: str, base_url: str, configured: str) -> LLMProtocol:
    if configured in {"responses", "openai_responses"}:
        return "responses"
    if configured in {"chat", "chat_completions", "openai_chat"}:
        return "chat_completions"
    normalized = f"{provider} {base_url}".lower()
    return "responses" if "cpl" in normalized or ":8082" in normalized else "chat_completions"


def _route_models(provider: str, settings: LLMSettings, base_url: str) -> tuple[str, ...] | None:
    """Return an exact configured roster or endpoint-discovered models.

    An explicit roster is authoritative. This prevents a provider catalog from
    silently adding a more expensive model to Cpl's council.
    """

    roster = configured_model_roster(provider)
    if roster:
        if settings.model and settings.model not in roster:
            return (settings.model, *roster)
        return roster
    try:
        return list_models(
            base_url,
            api_key=settings.api_key,
            timeout_seconds=min(settings.timeout_seconds, 4.0),
        )
    except LLMProviderError:
        if settings.model:
            return ()
        return None


def _build_route(provider_name: str, base_url: str, settings: LLMSettings) -> LLMRoute | None:
    models = _route_models(provider_name, settings, base_url)
    if models is None:
        return None
    model = select_model(models, settings.model)
    if not model:
        return None
    return LLMRoute(
        provider=provider_name,
        base_url=base_url,
        model=model,
        protocol=_protocol_for(provider_name, base_url, settings.protocol),
        api_key=settings.api_key,
        timeout_seconds=settings.timeout_seconds,
        max_output_tokens=settings.max_output_tokens,
        discovered_models=models,
    )


def discover_route(settings: LLMSettings | None = None) -> LLMRoute | None:
    settings = settings or LLMSettings.from_environment()
    if not settings.enabled:
        return None

    provider = _normalize_provider(settings.provider)
    explicit_base = _normalize_base_url(settings.base_url)

    # Cloudflare has an exact user-approved roster and does not need /models.
    # Keep this explicit so no network discovery can block a valid configuration.
    if provider == CLOUDFLARE_PROVIDER:
        if not explicit_base or not settings.api_key:
            return None
        return _build_route(provider, explicit_base, settings)

    if explicit_base:
        candidates = [(provider if provider != "auto" else "configured", explicit_base)]
    else:
        local_candidates = [
            ("cpl", DEFAULT_CPL_BASE_URL),
            ("ollama", DEFAULT_OLLAMA_BASE_URL),
            ("lm-studio", DEFAULT_LM_STUDIO_BASE_URL),
        ]
        candidates = local_candidates if provider == "auto" else [item for item in local_candidates if item[0] == provider]

    for provider_name, base_url in candidates:
        route = _build_route(provider_name, base_url, settings)
        if route is not None:
            return route
    return None


def _extract_text(payload: dict[str, Any], protocol: LLMProtocol) -> str:
    if protocol == "chat_completions":
        choices = payload.get("choices", [])
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [
                    str(item.get("text", ""))
                    for item in content
                    if isinstance(item, dict) and item.get("text")
                ]
                return "\n".join(parts)
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text
    output = payload.get("output", [])
    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content", [])
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        parts.append(part["text"])
        if parts:
            return "\n".join(parts)
    raise LLMProviderError("Cpl model response did not contain text output.")


def _parse_json_text(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            raise LLMProviderError("Cpl model output did not contain a JSON object.") from None
        try:
            payload = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as error:
            raise LLMProviderError("Cpl model output contained invalid JSON.") from error
    if not isinstance(payload, dict):
        raise LLMProviderError("Cpl model output JSON must be an object.")
    return payload


def invoke_json(route: LLMRoute, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    headers = _request_headers(route.api_key)
    if route.protocol == "responses":
        body: dict[str, Any] = {
            "model": route.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
            ],
            "temperature": 0,
            "max_output_tokens": route.max_output_tokens,
        }
        endpoint = f"{route.base_url}/responses"
    else:
        body = {
            "model": route.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "max_tokens": route.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        endpoint = f"{route.base_url}/chat/completions"

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        response = _load_json_response(request, route.timeout_seconds)
    except LLMProviderError as first_error:
        # Several compatible providers reject response_format while still
        # supporting JSON-only prompts. Retry once without that optional field.
        if route.protocol != "chat_completions" or "response_format" not in body:
            raise
        body.pop("response_format", None)
        retry = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            response = _load_json_response(retry, route.timeout_seconds)
        except LLMProviderError:
            raise first_error
    return _parse_json_text(_extract_text(response, route.protocol))


# Public Cpl aliases preserve the 0.4.0 Python API for integrations importing
# the earlier LLM* names.
CplProviderError = LLMProviderError
CplSettings = LLMSettings
CplRoute = LLMRoute
