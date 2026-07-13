"""Provider routing for Sergeant's optional semantic review layer.

The router deliberately speaks stable HTTP protocols instead of importing a
specific proxy implementation.  It can therefore use Free Claude Code (FCC),
any explicit OpenAI-compatible endpoint, Ollama, or LM Studio without making
those projects runtime dependencies of Sergeant.

Automatic discovery probes loopback endpoints only.  Remote code transmission
requires an explicit ``SERGEANT_LLM_BASE_URL`` configuration.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Literal

LLMProtocol = Literal["responses", "chat_completions"]
LLMPolicy = Literal["preferred", "required", "disabled"]

DEFAULT_FCC_BASE_URL = "http://127.0.0.1:8082/v1"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_LM_STUDIO_BASE_URL = "http://127.0.0.1:1234/v1"

# Order matters.  Sergeant first prefers the strongest deep coding route, then
# efficient coding-specialist and multimodal agentic routes.
PREFERRED_MODEL_NEEDLES = (
    "glm-5.2",
    "qwen3-coder-next",
    "kimi-k2.5",
    "glm-5.1",
    "qwen3-coder",
    "kimi-k2",
)


class LLMProviderError(RuntimeError):
    """Raised when a configured model endpoint cannot satisfy a request."""


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
        policy_raw = os.getenv("SERGEANT_LLM_POLICY", "preferred").strip().lower()
        policy: LLMPolicy = (
            policy_raw if policy_raw in {"preferred", "required", "disabled"} else "preferred"
        )  # type: ignore[assignment]
        enabled_raw = os.getenv("SERGEANT_LLM_ENABLED", "auto").strip().lower()
        enabled = policy != "disabled" and enabled_raw not in {"0", "false", "no", "off", "disabled"}
        return cls(
            enabled=enabled,
            policy=policy,
            provider=os.getenv("SERGEANT_LLM_PROVIDER", "auto").strip() or "auto",
            base_url=os.getenv("SERGEANT_LLM_BASE_URL", "").strip(),
            model=os.getenv("SERGEANT_LLM_MODEL", "").strip(),
            protocol=os.getenv("SERGEANT_LLM_PROTOCOL", "auto").strip().lower() or "auto",
            api_key=os.getenv("SERGEANT_LLM_API_KEY", "").strip(),
            timeout_seconds=_float_env("SERGEANT_LLM_TIMEOUT_SECONDS", 90.0, minimum=1.0, maximum=900.0),
            max_output_tokens=_int_env("SERGEANT_LLM_MAX_OUTPUT_TOKENS", 5000, minimum=256, maximum=32000),
        )

    def public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("api_key", None)
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
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "protocol": self.protocol,
            "timeout_seconds": self.timeout_seconds,
            "max_output_tokens": self.max_output_tokens,
            "discovered_models": list(self.discovered_models),
        }


def _float_env(name: str, default: float, *, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(maximum, max(minimum, value))


def _int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
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
        "User-Agent": "sergeant-reviewer/llm-router",
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
        raise LLMProviderError(f"LLM endpoint returned HTTP {error.code}: {detail}") from error
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as error:
        raise LLMProviderError(f"LLM endpoint is unavailable: {error}") from error

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        raise LLMProviderError("LLM endpoint returned a non-JSON response.") from error
    if not isinstance(payload, dict):
        raise LLMProviderError("LLM endpoint returned an unexpected JSON shape.")
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
    return "responses" if "fcc" in normalized or ":8082" in normalized else "chat_completions"


def discover_route(settings: LLMSettings | None = None) -> LLMRoute | None:
    settings = settings or LLMSettings.from_environment()
    if not settings.enabled:
        return None

    explicit_base = _normalize_base_url(settings.base_url)
    if explicit_base:
        candidates = [(settings.provider if settings.provider != "auto" else "configured", explicit_base)]
    else:
        provider = settings.provider.lower()
        local_candidates = [
            ("fcc", DEFAULT_FCC_BASE_URL),
            ("ollama", DEFAULT_OLLAMA_BASE_URL),
            ("lm-studio", DEFAULT_LM_STUDIO_BASE_URL),
        ]
        candidates = local_candidates if provider == "auto" else [item for item in local_candidates if item[0] == provider]

    for provider_name, base_url in candidates:
        try:
            models = list_models(
                base_url,
                api_key=settings.api_key,
                timeout_seconds=min(settings.timeout_seconds, 4.0),
            )
        except LLMProviderError:
            # An explicitly configured endpoint may hide model listing while still
            # accepting requests.  A configured model is enough to try it.
            if explicit_base and settings.model:
                models = ()
            else:
                continue
        model = select_model(models, settings.model)
        if not model:
            continue
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
    raise LLMProviderError("LLM response did not contain text output.")


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
            raise LLMProviderError("LLM output did not contain a JSON object.")
        try:
            payload = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as error:
            raise LLMProviderError("LLM output contained invalid JSON.") from error
    if not isinstance(payload, dict):
        raise LLMProviderError("LLM output JSON must be an object.")
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
        # Several OpenAI-compatible providers reject response_format while still
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
