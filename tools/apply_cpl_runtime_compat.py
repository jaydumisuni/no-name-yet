from __future__ import annotations

from pathlib import Path


path = Path(__file__).parents[1] / "main_review" / "cpl_runtime.py"
text = path.read_text(encoding="utf-8")

replacements = [
    (
        "from .llm_provider import LLMProviderError, LLMRoute, LLMSettings, discover_route\n",
        "from .llm_provider import LLMProviderError, LLMRoute, LLMSettings, discover_route, invoke_json\n",
    ),
    (
        "    _invoke_json_with_failover,\n",
        "",
    ),
    (
        "\n\ndef _coverage(passes: list[dict[str, Any]], original: dict[str, Any]) -> dict[str, Any]:\n",
        '''\n\ndef _invoke_follow_up_with_failover(\n    route: LLMRoute,\n    *,\n    system_prompt: str,\n    user_prompt: str,\n) -> tuple[dict[str, Any], LLMRoute, list[str]]:\n    """Preserve the runtime transport seam while rerouting failed council members."""\n\n    failed_models: list[str] = []\n    for model in available_models(route):\n        candidate = replace(route, model=model)\n        try:\n            return (\n                invoke_json(candidate, system_prompt=system_prompt, user_prompt=user_prompt),\n                candidate,\n                failed_models,\n            )\n        except LLMProviderError:\n            failed_models.append(model)\n    raise LLMProviderError(\n        "No configured Cpl council model completed the follow-up officer pass."\n    )\n\n\ndef _coverage(passes: list[dict[str, Any]], original: dict[str, Any]) -> dict[str, Any]:\n''',
    ),
    (
        "payload, completed_route, failed_models = _invoke_json_with_failover(\n",
        "payload, completed_route, failed_models = _invoke_follow_up_with_failover(\n",
    ),
]

for old, new in replacements:
    if new in text:
        continue
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one compatibility marker, found {count}: {old[:80]!r}")
    text = text.replace(old, new, 1)

if text.count("def _invoke_follow_up_with_failover(") != 1:
    raise SystemExit("Runtime failover helper must be defined exactly once.")
if "from .llm_provider import LLMProviderError, LLMRoute, LLMSettings, discover_route, invoke_json" not in text:
    raise SystemExit("Runtime invoke_json compatibility seam was not restored.")

path.write_text(text, encoding="utf-8")
print("Cpl runtime transport compatibility restored.")
