"""Cloudflare Workers AI presets for Sergeant's provider-neutral Cpl council.

The model identifiers are public catalog values. Account IDs and API tokens are
never stored here; users supply them through environment variables or their
secret manager.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

CLOUDFLARE_PROVIDER = "cloudflare"
CLOUDFLARE_PROVIDER_ALIASES = {
    CLOUDFLARE_PROVIDER,
    "cloudflare-workers-ai",
    "workers-ai",
    "cf",
}
CLOUDFLARE_BASE_TEMPLATE = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1"
_ACCOUNT_ID_RE = re.compile(r"^[A-Fa-f0-9]{32}$")

# Broad passes use efficient reasoning models. Expensive specialists are placed
# later so Cpl recruits them only when earlier passes leave a real evidence gap.
CLOUDFLARE_FREE_BALANCED_MODELS = (
    "@cf/qwen/qwen3-30b-a3b-fp8",
    "@cf/zai-org/glm-4.7-flash",
    "@cf/openai/gpt-oss-20b",
    "@cf/qwen/qwen2.5-coder-32b-instruct",
)

CLOUDFLARE_FREE_STRONG_MODELS = (
    *CLOUDFLARE_FREE_BALANCED_MODELS,
    "@cf/openai/gpt-oss-120b",
    "@cf/moonshotai/kimi-k2.7-code",
)

CLOUDFLARE_FREE_EFFICIENT_MODELS = (
    "@cf/qwen/qwen3-30b-a3b-fp8",
    "@cf/zai-org/glm-4.7-flash",
    "@cf/ibm-granite/granite-4.0-h-micro",
)

MODEL_PRESETS: dict[str, tuple[str, ...]] = {
    "cloudflare-free-efficient": CLOUDFLARE_FREE_EFFICIENT_MODELS,
    "cloudflare-free-balanced": CLOUDFLARE_FREE_BALANCED_MODELS,
    "cloudflare-free-strong": CLOUDFLARE_FREE_STRONG_MODELS,
}
DEFAULT_CLOUDFLARE_PRESET = "cloudflare-free-balanced"

CLOUDFLARE_REASONING_MODELS = {
    "@cf/qwen/qwen3-30b-a3b-fp8",
    "@cf/zai-org/glm-4.7-flash",
    "@cf/openai/gpt-oss-20b",
    "@cf/openai/gpt-oss-120b",
}
DEFAULT_MODEL_PROOF_OUTPUT_TOKENS = 384
REASONING_MODEL_PROOF_OUTPUT_TOKENS = 900


@dataclass(frozen=True)
class CloudflareModelProfile:
    model: str
    tier: str
    purpose: str
    input_neurons_per_million: int | None
    output_neurons_per_million: int | None


MODEL_PROFILES: dict[str, CloudflareModelProfile] = {
    "@cf/qwen/qwen3-30b-a3b-fp8": CloudflareModelProfile(
        "@cf/qwen/qwen3-30b-a3b-fp8",
        "broad",
        "Efficient primary reasoning and instruction-following council member.",
        4625,
        30475,
    ),
    "@cf/zai-org/glm-4.7-flash": CloudflareModelProfile(
        "@cf/zai-org/glm-4.7-flash",
        "broad",
        "Independent challenger and agentic second opinion.",
        5500,
        36400,
    ),
    "@cf/ibm-granite/granite-4.0-h-micro": CloudflareModelProfile(
        "@cf/ibm-granite/granite-4.0-h-micro",
        "broad",
        "Very low-cost Scout, summarization, and structured extraction pass.",
        1542,
        10158,
    ),
    "@cf/openai/gpt-oss-20b": CloudflareModelProfile(
        "@cf/openai/gpt-oss-20b",
        "specialist",
        "Stronger independent adjudication and difficult specialist pass.",
        18182,
        27273,
    ),
    "@cf/qwen/qwen2.5-coder-32b-instruct": CloudflareModelProfile(
        "@cf/qwen/qwen2.5-coder-32b-instruct",
        "specialist",
        "Narrow code specialist used after Cpl identifies a concrete gap.",
        60000,
        90909,
    ),
    "@cf/openai/gpt-oss-120b": CloudflareModelProfile(
        "@cf/openai/gpt-oss-120b",
        "examiner",
        "Rare high-reasoning examiner, never a routine broad-pass model.",
        31818,
        68182,
    ),
    "@cf/moonshotai/kimi-k2.7-code": CloudflareModelProfile(
        "@cf/moonshotai/kimi-k2.7-code",
        "examiner",
        "Rare frontier coding examiner for unresolved agentic code investigations.",
        None,
        None,
    ),
}


def model_proof_output_tokens(model: str) -> int:
    """Return a small but viable structured-proof budget for a model."""

    return (
        REASONING_MODEL_PROOF_OUTPUT_TOKENS
        if model in CLOUDFLARE_REASONING_MODELS
        else DEFAULT_MODEL_PROOF_OUTPUT_TOKENS
    )


def parse_model_list(value: str) -> tuple[str, ...]:
    """Parse a comma/newline model roster while preserving first occurrence."""

    items = [item.strip() for item in value.replace("\n", ",").split(",")]
    return tuple(dict.fromkeys(item for item in items if item))


def is_cloudflare_provider(provider: str) -> bool:
    """Return whether a provider name resolves to Cloudflare Workers AI."""

    return provider.strip().lower() in CLOUDFLARE_PROVIDER_ALIASES


def cloudflare_base_url(account_id: str) -> str:
    """Return a Workers AI OpenAI-compatible base URL for a valid Account ID."""

    account_id = account_id.strip()
    if not account_id or not _ACCOUNT_ID_RE.fullmatch(account_id):
        return ""
    return CLOUDFLARE_BASE_TEMPLATE.format(account_id=account_id)


def configured_model_roster(provider: str, explicit: str | None = None) -> tuple[str, ...]:
    """Resolve an exact roster or a named public preset.

    For Cloudflare, ``SERGEANT_CLOUDFLARE_MODELS`` is the most specific public
    override. ``SERGEANT_CPL_MODELS`` remains the provider-neutral override. A
    supplied ``explicit`` value is used by callers that already read their own
    environment contract. The balanced preset is the shared default for the
    direct route, local gateway, website and IDE connectors.
    """

    candidates = [explicit or ""]
    if is_cloudflare_provider(provider):
        candidates.append(os.getenv("SERGEANT_CLOUDFLARE_MODELS", ""))
    candidates.append(os.getenv("SERGEANT_CPL_MODELS", ""))
    for value in candidates:
        roster = parse_model_list(value)
        if roster:
            return roster

    preset_name = os.getenv("SERGEANT_CPL_MODEL_PRESET", "").strip().lower()
    if not preset_name and is_cloudflare_provider(provider):
        preset_name = DEFAULT_CLOUDFLARE_PRESET
    return MODEL_PRESETS.get(preset_name, ())


def cloudflare_environment() -> tuple[str, str]:
    """Return derived base URL and API token without exposing either publicly."""

    account_id = os.getenv("SERGEANT_CLOUDFLARE_ACCOUNT_ID", "")
    token = os.getenv("SERGEANT_CLOUDFLARE_API_TOKEN", "").strip()
    return cloudflare_base_url(account_id), token


def public_base_url(provider: str, base_url: str) -> str:
    """Mask the Cloudflare Account ID in diagnostics and proof artifacts."""

    if not is_cloudflare_provider(provider):
        return base_url
    return re.sub(r"/accounts/[^/]+/", "/accounts/***/", base_url)
