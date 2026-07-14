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
CLOUDFLARE_BASE_TEMPLATE = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1"
_ACCOUNT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")

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


@dataclass(frozen=True)
class CloudflareModelProfile:
    model: str
    tier: str
    purpose: str
    input_neurons_per_million: int
    output_neurons_per_million: int


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
}


def parse_model_list(value: str) -> tuple[str, ...]:
    """Parse a comma/newline model roster while preserving first occurrence."""

    items = [item.strip() for item in value.replace("\n", ",").split(",")]
    return tuple(dict.fromkeys(item for item in items if item))


def cloudflare_base_url(account_id: str) -> str:
    """Return a Workers AI OpenAI-compatible base URL for a safe Account ID."""

    account_id = account_id.strip()
    if not account_id or not _ACCOUNT_ID_RE.fullmatch(account_id):
        return ""
    return CLOUDFLARE_BASE_TEMPLATE.format(account_id=account_id)


def configured_model_roster(provider: str) -> tuple[str, ...]:
    """Resolve an explicit roster or a named public preset.

    ``SERGEANT_CPL_MODELS`` always wins. Cloudflare defaults to the balanced
    free-allocation preset so a user needs only an Account ID and scoped token.
    Other providers receive no implicit roster.
    """

    explicit = parse_model_list(os.getenv("SERGEANT_CPL_MODELS", ""))
    if explicit:
        return explicit

    preset_name = os.getenv("SERGEANT_CPL_MODEL_PRESET", "").strip().lower()
    if not preset_name and provider.strip().lower() == CLOUDFLARE_PROVIDER:
        preset_name = DEFAULT_CLOUDFLARE_PRESET
    return MODEL_PRESETS.get(preset_name, ())


def cloudflare_environment() -> tuple[str, str]:
    """Return derived base URL and API token without exposing either publicly."""

    account_id = os.getenv("SERGEANT_CLOUDFLARE_ACCOUNT_ID", "")
    token = os.getenv("SERGEANT_CLOUDFLARE_API_TOKEN", "").strip()
    return cloudflare_base_url(account_id), token


def public_base_url(provider: str, base_url: str) -> str:
    """Mask the Cloudflare Account ID in diagnostics and proof artifacts."""

    if provider.strip().lower() != CLOUDFLARE_PROVIDER:
        return base_url
    return re.sub(r"/accounts/[^/]+/", "/accounts/***/", base_url)
