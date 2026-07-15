from pathlib import Path

models = Path("main_review/cloudflare_models.py")
text = models.read_text(encoding="utf-8")
marker = 'DEFAULT_CLOUDFLARE_PRESET = "cloudflare-free-balanced"\n'
text = text.replace(
    marker,
    marker
    + '''\nCLOUDFLARE_REASONING_MODELS = {\n    "@cf/qwen/qwen3-30b-a3b-fp8",\n    "@cf/zai-org/glm-4.7-flash",\n    "@cf/openai/gpt-oss-20b",\n    "@cf/openai/gpt-oss-120b",\n}\nDEFAULT_MODEL_PROOF_OUTPUT_TOKENS = 384\nREASONING_MODEL_PROOF_OUTPUT_TOKENS = 900\n''',
)
anchor = "def parse_model_list(value: str) -> tuple[str, ...]:\n"
text = text.replace(
    anchor,
    '''def model_proof_output_tokens(model: str) -> int:\n    """Return a small but viable structured-proof budget for a model."""\n\n    return (\n        REASONING_MODEL_PROOF_OUTPUT_TOKENS\n        if model in CLOUDFLARE_REASONING_MODELS\n        else DEFAULT_MODEL_PROOF_OUTPUT_TOKENS\n    )\n\n\n'''
    + anchor,
)
models.write_text(text, encoding="utf-8")

cli = Path("main_review/cloudflare_cli.py")
text = cli.read_text(encoding="utf-8")
text = text.replace(
    "from .cloudflare_gateway import (\n",
    "from .cloudflare_models import model_proof_output_tokens\nfrom .cloudflare_gateway import (\n",
)
text = text.replace("MODEL_PROOF_MAX_OUTPUT_TOKENS = 320\n", "")
text = text.replace(
    '''        route = cloudflare_route(\n            settings,\n            model=model,\n            max_output_tokens=MODEL_PROOF_MAX_OUTPUT_TOKENS,\n        )\n''',
    '''        proof_tokens = model_proof_output_tokens(model)\n        route = cloudflare_route(\n            settings,\n            model=model,\n            max_output_tokens=proof_tokens,\n        )\n''',
)
text = text.replace(
    '                    "duration_ms": round((time.monotonic() - started) * 1000, 2),\n                    "response": payload,\n',
    '                    "duration_ms": round((time.monotonic() - started) * 1000, 2),\n                    "max_output_tokens": proof_tokens,\n                    "response": payload,\n',
)
text = text.replace(
    '                    "duration_ms": round((time.monotonic() - started) * 1000, 2),\n                    "error": str(error),\n',
    '                    "duration_ms": round((time.monotonic() - started) * 1000, 2),\n                    "max_output_tokens": proof_tokens,\n                    "error": str(error),\n',
)
cli.write_text(text, encoding="utf-8")
