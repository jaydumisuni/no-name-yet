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
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Literal

from .cloudflare_models import (
    CLOUDFLARE_PROVIDER,
    cloudflare_environment,
    configured_model_roster,
    is_cloudflare_provider,
    public_base_url,
)
from .cloudflare_usage import (
    CloudflareUsageError,
    mark_cloudflare_quota_blocked,
    reserve_cloudflare_request,
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
    """Raised when a configured Cpl model endpoint cannot satisfy a request.

    ``failed_models`` preserves credential-safe route-attempt provenance when
    every configured model fails. Callers can therefore audit and resume the
    council formation without copying provider response bodies into evidence.
    """

    def __init__(self, message: str, *, failed_models: Iterable[str] = ()) -> None:
        super().__init__(message)
        self.failed_models = tuple(dict.fromkeys(str(model) for model in failed_models if str(model)))


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


def is_cloudflare_quota_error(error: BaseException) -> bool:
    """Return whether an error represents the Workers AI daily-allocation limit."""

    message = str(error).lower()
    return bool(
        "code 4006" in message
        or '"code":4006' in message
        or "daily free allocation" in message
        or "daily allocation is exhausted" in message
        or "quota circuit is open" in message
    )


def is_http_rate_limit_error(error: BaseException) -> bool:
    """Return whether the provider rejected a request with generic HTTP 429."""

    return "http 429" in str(error).lower()


def _load_model_response(
    route: LLMRoute,
    request: urllib.request.Request,
    *,
    system_prompt: str,
    user_prompt: str,
    stage: str,
) -> dict[str, Any]:
    if is_cloudflare_provider(route.provider):
        try:
            reserve_cloudflare_request(
                model=route.model,
                input_chars=len(system_prompt) + len(user_prompt),
                max_output_tokens=route.max_output_tokens,
                stage=stage,
            )
        except CloudflareUsageError as error:
            raise LLMProviderError(str(error)) from error
    try:
        return _load_json_response(request, route.timeout_seconds)
    except LLMProviderError as error:
        if is_cloudflare_provider(route.provider) and is_cloudflare_quota_error(error):
            state = mark_cloudflare_quota_blocked()
            reset_at = str(state.get("reset_at") or "the next UTC day")
            raise LLMProviderError(
                "Cloudflare daily inference allocation is exhausted "
                f"(HTTP 429 / code 4006); quota circuit opened until {reset_at}."
            ) from error
        raise


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


def _response_shape(payload: dict[str, Any]) -> str:
    """Return a credential-safe summary of a provider response structure."""

    shape: dict[str, object] = {"top_level_keys": sorted(str(key) for key in payload)}
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        first = choices[0]
        shape["choice_keys"] = sorted(str(key) for key in first)
        message = first.get("message")
        if isinstance(message, dict):
            shape["message_keys"] = sorted(str(key) for key in message)
        if first.get("finish_reason") is not None:
            shape["finish_reason"] = str(first.get("finish_reason"))
    result = payload.get("result")
    if isinstance(result, dict):
        shape["result_keys"] = sorted(str(key) for key in result)
    return json.dumps(shape, sort_keys=True)


_STRUCTURED_MODEL_KEYS = frozenset(
    {
        "status",
        "verdict",
        "finding",
        "findings",
        "coverage",
        "facts",
        "capabilities",
        "claims",
        "decision",
    }
)


def _structured_model_object(value: object) -> dict[str, Any] | None:
    """Return an already-structured model payload, excluding provider metadata."""

    if not isinstance(value, dict):
        return None
    keys = {str(key) for key in value}
    return value if keys & _STRUCTURED_MODEL_KEYS else None


def _text_value(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, dict):
        for key in ("text", "content", "value", "response", "output"):
            text = _text_value(value.get(key))
            if text:
                return text
        structured = _structured_model_object(value)
        if structured is not None:
            return json.dumps(structured, sort_keys=True)
        return ""
    if isinstance(value, list):
        parts = [_text_value(item) for item in value]
        return "\n".join(part for part in parts if part)
    return ""


def _extract_text(payload: dict[str, Any], protocol: LLMProtocol) -> str:
    if protocol == "chat_completions":
        choices = payload.get("choices", [])
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            first = choices[0]
            message = first.get("message", {})
            if isinstance(message, dict):
                for key in ("content", "reasoning_content", "reasoning", "analysis"):
                    content = _text_value(message.get(key))
                    if content:
                        return content
            choice_text = _text_value(first.get("text"))
            if choice_text:
                return choice_text

    for key in ("response", "output_text", "generated_text", "text", "reasoning_content", "reasoning", "analysis"):
        value = _text_value(payload.get(key))
        if value:
            return value

    result = payload.get("result")
    if isinstance(result, dict):
        for key in ("response", "output_text", "generated_text", "text", "output", "reasoning_content", "reasoning", "analysis"):
            value = _text_value(result.get(key))
            if value:
                return value

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

    raise LLMProviderError(
        "Cpl model response did not contain text output. "
        f"Response shape: {_response_shape(payload)}"
    )


def _json_candidate_score(payload: dict[str, Any]) -> int:
    keys = {str(key) for key in payload}
    important = {"verdict", "findings", "coverage", "status", "model", "capabilities"}
    return len(keys & important) * 10


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
        decoder = json.JSONDecoder()
        objects: list[tuple[int, dict[str, Any]]] = []
        for index, character in enumerate(candidate):
            if character != "{":
                continue
            try:
                value, _ = decoder.raw_decode(candidate[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                objects.append((index, value))
        if not objects:
            raise LLMProviderError("Cpl model output did not contain a parseable JSON object.") from None
        payload = max(
            objects,
            key=lambda item: (_json_candidate_score(item[1]), item[0]),
        )[1]
    if not isinstance(payload, dict):
        raise LLMProviderError("Cpl model output JSON must be an object.")
    return payload


def _cloudflare_native_endpoint(route: LLMRoute) -> str:
    base = route.base_url.rstrip("/")
    if base.endswith("/ai/v1"):
        base = base[:-3]
    elif base.endswith("/v1"):
        base = base[:-3]
    model = urllib.parse.quote(route.model, safe="@/")
    return f"{base}/run/{model}"


def _invoke_cloudflare_native_text(
    route: LLMRoute,
    *,
    system_prompt: str,
    user_prompt: str,
) -> str:
    body = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": route.max_output_tokens,
    }
    request = urllib.request.Request(
        _cloudflare_native_endpoint(route),
        data=json.dumps(body).encode("utf-8"),
        headers=_request_headers(route.api_key),
        method="POST",
    )
    response = _load_model_response(
        route,
        request,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        stage="native_fallback",
    )
    return _extract_text(response, "chat_completions")


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
        response = _load_model_response(
            route,
            request,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            stage="openai_compatible",
        )
    except LLMProviderError as first_error:
        if (
            is_cloudflare_quota_error(first_error)
            or is_http_rate_limit_error(first_error)
            or route.protocol != "chat_completions"
            or "response_format" not in body
        ):
            raise
        body.pop("response_format", None)
        retry = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            response = _load_model_response(
                route,
                retry,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                stage="openai_compatible_without_response_format",
            )
        except LLMProviderError as retry_error:
            if is_cloudflare_quota_error(retry_error):
                raise
            raise first_error

    try:
        return _parse_json_text(_extract_text(response, route.protocol))
    except LLMProviderError:
        if not is_cloudflare_provider(route.provider):
            raise
        try:
            native_text = _invoke_cloudflare_native_text(
                route,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            return _parse_json_text(native_text)
        except LLMProviderError as native_error:
            if is_cloudflare_quota_error(native_error):
                raise
            raise LLMProviderError(
                "Cloudflare OpenAI-compatible and native model routes both failed without a parseable JSON response."
            ) from native_error


# Public Cpl aliases preserve the 0.4.0 Python API for integrations importing
# the earlier LLM* names.
CplProviderError = LLMProviderError
CplSettings = LLMSettings
CplRoute = LLMRoute
