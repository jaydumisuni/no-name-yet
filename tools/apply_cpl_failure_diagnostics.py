from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if new and new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one marker in {relative}, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Clean stale imports left by the runtime transport compatibility bridge.
replace_once("main_review/cpl_runtime.py", "    finding_key,\n", "")
replace_once("main_review/cpl_runtime.py", "    _invoke_json_with_failover,\n", "")

# Normalize support identities without turning null into a fake model named 'None'.
replace_once(
    "main_review/cpl_noise.py",
    "\nSEVERITY_RANK = {\"note\": 0, \"minor\": 1, \"major\": 2, \"blocker\": 3}\n",
    "\n",
)
replace_once(
    "main_review/cpl_noise.py",
    "    return sorted({str(value) for value in values if str(value).strip()})\n",
    "    return sorted({str(value) for value in values if value is not None and str(value).strip()})\n",
)

# Preserve only credential-safe provider failure classes when every model fails.
llm_path = ROOT / "main_review" / "llm_review.py"
llm_text = llm_path.read_text(encoding="utf-8")
old_helper = '''def _invoke_json_with_failover(\n    route: LLMRoute,\n    *,\n    system_prompt: str,\n    user_prompt: str,\n) -> tuple[dict[str, Any], LLMRoute, list[str]]:\n    """Try each configured council model before declaring the officer pass failed."""\n\n    failed_models: list[str] = []\n    for model in available_models(route):\n        candidate = replace(route, model=model)\n        try:\n            return (\n                invoke_json(candidate, system_prompt=system_prompt, user_prompt=user_prompt),\n                candidate,\n                failed_models,\n            )\n        except LLMProviderError:\n            failed_models.append(model)\n    raise LLMProviderError(\n        "No configured Cpl council model completed the required structured officer pass."\n    )\n'''
new_helper = '''def _provider_failure_kind(error: LLMProviderError) -> str:\n    """Return a credential-safe provider failure category for audit and retry policy."""\n\n    message = str(error)\n    status = re.search(r"\\bHTTP\\s+(\\d{3})\\b", message, flags=re.IGNORECASE)\n    if status:\n        return f"http_{status.group(1)}"\n    lowered = message.lower()\n    if "timed out" in lowered or "timeout" in lowered:\n        return "timeout"\n    if "unavailable" in lowered or "urlopen error" in lowered:\n        return "unavailable"\n    if "invalid json" in lowered or "non-json" in lowered:\n        return "invalid_json"\n    if "did not contain" in lowered or "unexpected json shape" in lowered:\n        return "response_contract"\n    return "provider_error"\n\n\ndef _provider_failure_summary(errors: list[LLMProviderError]) -> str:\n    counts: dict[str, int] = {}\n    for error in errors:\n        kind = _provider_failure_kind(error)\n        counts[kind] = counts.get(kind, 0) + 1\n    return ", ".join(f"{kind}={counts[kind]}" for kind in sorted(counts))\n\n\ndef _invoke_json_with_failover(\n    route: LLMRoute,\n    *,\n    system_prompt: str,\n    user_prompt: str,\n) -> tuple[dict[str, Any], LLMRoute, list[str]]:\n    """Try each configured council model before declaring the officer pass failed."""\n\n    failed_models: list[str] = []\n    failures: list[LLMProviderError] = []\n    for model in available_models(route):\n        candidate = replace(route, model=model)\n        try:\n            return (\n                invoke_json(candidate, system_prompt=system_prompt, user_prompt=user_prompt),\n                candidate,\n                failed_models,\n            )\n        except LLMProviderError as error:\n            failed_models.append(model)\n            failures.append(error)\n    summary = _provider_failure_summary(failures)\n    suffix = f" ({summary})" if summary else ""\n    raise LLMProviderError(\n        "No configured Cpl council model completed the required structured officer pass"\n        f"{suffix}."\n    )\n'''
if new_helper not in llm_text:
    if llm_text.count(old_helper) != 1:
        raise SystemExit("Expected exactly one primary failover helper.")
    llm_path.write_text(llm_text.replace(old_helper, new_helper, 1), encoding="utf-8")

# Reuse the same safe summary for recruited follow-up passes.
replace_once(
    "main_review/cpl_runtime.py",
    "    _merge_passes,\n",
    "    _merge_passes,\n    _provider_failure_summary,\n",
)
runtime_path = ROOT / "main_review" / "cpl_runtime.py"
runtime_text = runtime_path.read_text(encoding="utf-8")
old_runtime = '''    failed_models: list[str] = []\n    for model in available_models(route):\n        candidate = replace(route, model=model)\n        try:\n            return (\n                invoke_json(candidate, system_prompt=system_prompt, user_prompt=user_prompt),\n                candidate,\n                failed_models,\n            )\n        except LLMProviderError:\n            failed_models.append(model)\n    raise LLMProviderError(\n        "No configured Cpl council model completed the follow-up officer pass."\n    )\n'''
new_runtime = '''    failed_models: list[str] = []\n    failures: list[LLMProviderError] = []\n    for model in available_models(route):\n        candidate = replace(route, model=model)\n        try:\n            return (\n                invoke_json(candidate, system_prompt=system_prompt, user_prompt=user_prompt),\n                candidate,\n                failed_models,\n            )\n        except LLMProviderError as error:\n            failed_models.append(model)\n            failures.append(error)\n    summary = _provider_failure_summary(failures)\n    suffix = f" ({summary})" if summary else ""\n    raise LLMProviderError(\n        "No configured Cpl council model completed the follow-up officer pass"\n        f"{suffix}."\n    )\n'''
if new_runtime not in runtime_text:
    if runtime_text.count(old_runtime) != 1:
        raise SystemExit("Expected exactly one follow-up failover helper.")
    runtime_path.write_text(runtime_text.replace(old_runtime, new_runtime, 1), encoding="utf-8")

# Document the safe all-route failure contract.
replace_once(
    "docs/38-cpl-noise-governor-and-route-failover.md",
    "If every configured model fails, the pass remains failed and Sergeant preserves the required-route error honestly.\n",
    "If every configured model fails, the pass remains failed and Sergeant preserves the required-route error honestly. The final error exposes only a safe category summary such as `http_429=2`, `timeout=1`, or `response_contract=1`; upstream response bodies are not copied into the council packet.\n",
)

# Add focused regressions from the live quota failure and source inspection.
test_path = ROOT / "tests" / "test_cpl_noise_governor.py"
test_text = test_path.read_text(encoding="utf-8")
insert = '''\n\ndef test_same_family_findings_remain_separate_when_far_apart() -> None:\n    left = {**cpl_shell(), "line_start": 5, "line_end": 5}\n    right = {**deterministic_shell(), "line_start": 50, "line_end": 50}\n\n    assert findings_overlap(left, right) is False\n\n\ndef test_supporting_model_normalization_drops_null_values() -> None:\n    major = {\n        "category": "correctness",\n        "severity": "major",\n        "message": "Returned value violates the documented contract.",\n        "evidence": "return None",\n        "evidence_verified": True,\n        "path": "src/app.py",\n        "line_start": 8,\n        "line_end": 8,\n        "supporting_models": [None, "model-a", "model-b"],\n    }\n\n    result = reconcile_cpl_findings(\n        {"status": "completed", "verdict": "NEEDS WORK", "findings": [major]},\n        [],\n    )\n\n    assert result["actionable_findings"][0]["supporting_models"] == ["model-a", "model-b"]\n\n\ndef test_all_model_failures_report_only_safe_failure_categories(monkeypatch: pytest.MonkeyPatch) -> None:\n    route = LLMRoute(\n        provider="cloudflare",\n        base_url="https://example.invalid/v1",\n        model="model-a",\n        protocol="chat_completions",\n        discovered_models=("model-a", "model-b"),\n    )\n\n    def fail(candidate: LLMRoute, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:\n        raise LLMProviderError(\n            "Cpl model endpoint returned HTTP 429: private upstream response text"\n        )\n\n    monkeypatch.setattr(llm_review, "invoke_json", fail)\n\n    with pytest.raises(LLMProviderError) as captured:\n        llm_review._invoke_json_with_failover(\n            route,\n            system_prompt="system",\n            user_prompt="user",\n        )\n\n    message = str(captured.value)\n    assert "http_429=2" in message\n    assert "private upstream response text" not in message\n'''
marker = "\n\ndef test_final_decision_uses_noise_governed_cpl_verdict() -> None:\n"
if insert.strip() not in test_text:
    if test_text.count(marker) != 1:
        raise SystemExit("Expected final-decision test marker once.")
    test_path.write_text(test_text.replace(marker, insert + marker, 1), encoding="utf-8")

# Final construction invariants.
checks = {
    "main_review/cpl_runtime.py": [
        ("finding_key,", 0),
        ("_invoke_json_with_failover,", 0),
        ("def _invoke_follow_up_with_failover(", 1),
        ("_provider_failure_summary,", 1),
    ],
    "main_review/llm_review.py": [
        ("def _provider_failure_kind(", 1),
        ("def _provider_failure_summary(", 1),
        ("def _invoke_json_with_failover(", 1),
    ],
}
for relative, markers in checks.items():
    text = (ROOT / relative).read_text(encoding="utf-8")
    for marker, expected in markers:
        if text.count(marker) != expected:
            raise SystemExit(f"Expected {expected} occurrences of {marker!r} in {relative}")

print("Cpl safe failure diagnostics and cleanup applied.")
