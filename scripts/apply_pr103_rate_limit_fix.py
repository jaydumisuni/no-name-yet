from pathlib import Path

path = Path("main_review/llm_provider.py")
text = path.read_text(encoding="utf-8")
old = '''def _load_model_response(\n    route: LLMRoute,\n'''
new = '''def is_http_rate_limit_error(error: BaseException) -> bool:\n    """Return whether the provider rejected a request with generic HTTP 429."""\n\n    return "http 429" in str(error).lower()\n\n\ndef _load_model_response(\n    route: LLMRoute,\n'''
if old not in text:
    raise SystemExit("load response marker missing")
text = text.replace(old, new, 1)
old = '''        if (\n            is_cloudflare_quota_error(first_error)\n            or route.protocol != "chat_completions"\n            or "response_format" not in body\n        ):\n'''
new = '''        if (\n            is_cloudflare_quota_error(first_error)\n            or is_http_rate_limit_error(first_error)\n            or route.protocol != "chat_completions"\n            or "response_format" not in body\n        ):\n'''
if old not in text:
    raise SystemExit("retry condition missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
