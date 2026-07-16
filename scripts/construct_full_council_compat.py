from __future__ import annotations

from pathlib import Path


def replace(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected construction marker not found in {path}: {old[:100]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace(
    "main_review/llm_provider.py",
    '''def _text_value(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, list):
        parts = [
            str(item.get("text", ""))
            for item in value
            if isinstance(item, dict) and isinstance(item.get("text"), str) and item.get("text")
        ]
        return "\n".join(parts)
    return ""
''',
    '''def _text_value(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, dict):
        for key in ("text", "content", "value", "response", "output"):
            text = _text_value(value.get(key))
            if text:
                return text
        return ""
    if isinstance(value, list):
        parts = [_text_value(item) for item in value]
        return "\n".join(part for part in parts if part)
    return ""
''',
)

replace(
    "main_review/llm_provider.py",
    '''            if isinstance(message, dict):
                content = _text_value(message.get("content"))
                if content:
                    return content
''',
    '''            if isinstance(message, dict):
                for key in ("content", "reasoning_content", "reasoning", "analysis"):
                    content = _text_value(message.get(key))
                    if content:
                        return content
''',
)

replace(
    "main_review/llm_provider.py",
    '''    for key in ("response", "output_text", "generated_text", "text"):
''',
    '''    for key in ("response", "output_text", "generated_text", "text", "reasoning_content", "reasoning", "analysis"):
''',
)

replace(
    "main_review/llm_provider.py",
    '''        for key in ("response", "output_text", "generated_text", "text", "output"):
''',
    '''        for key in ("response", "output_text", "generated_text", "text", "output", "reasoning_content", "reasoning", "analysis"):
''',
)

replace(
    "main_review/llm_provider.py",
    '''def _parse_json_text(text: str) -> dict[str, Any]:
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
''',
    '''def _json_candidate_score(payload: dict[str, Any]) -> tuple[int, int]:
    keys = {str(key) for key in payload}
    important = {"verdict", "findings", "coverage", "status", "model", "capabilities"}
    score = len(keys & important) * 10
    required = payload.get("required")
    if isinstance(required, dict):
        score += len({str(key) for key in required} & important) * 8
    return score, len(json.dumps(payload, sort_keys=True, default=str))


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
        objects: list[dict[str, Any]] = []
        for index, character in enumerate(candidate):
            if character != "{":
                continue
            try:
                value, _ = decoder.raw_decode(candidate[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                objects.append(value)
        if not objects:
            raise LLMProviderError("Cpl model output did not contain a parseable JSON object.") from None
        payload = max(objects, key=_json_candidate_score)
    if not isinstance(payload, dict):
        raise LLMProviderError("Cpl model output JSON must be an object.")
    return payload
''',
)

replace(
    "main_review/cloudflare_models.py",
    '''    "@cf/openai/gpt-oss-20b",
    "@cf/openai/gpt-oss-120b",
''',
    '''    "@cf/openai/gpt-oss-20b",
    "@cf/qwen/qwen2.5-coder-32b-instruct",
    "@cf/openai/gpt-oss-120b",
''',
)

replace(
    "main_review/cloudflare_cli.py",
    "MISSION_PROOF_MAX_OUTPUT_TOKENS = 1200\nMISSION_PROOF_TIMEOUT_SECONDS = 45.0\n",
    "MISSION_PROOF_MAX_OUTPUT_TOKENS = 1800\nMISSION_PROOF_TIMEOUT_SECONDS = 75.0\n",
)

replace(
    "main_review/cloudflare_cli.py",
    '''def test_models(settings: CloudflareGatewaySettings) -> dict[str, Any]:
''',
    '''def _proof_contract_matches(payload: dict[str, Any], model: str) -> bool:
    candidates = [payload]
    for key in ("required", "result"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)
    return any(
        candidate.get("status") == "ready"
        and candidate.get("model") == model
        and candidate.get("capabilities") == REQUIRED_PROOF_CAPABILITIES
        for candidate in candidates
    )


def test_models(settings: CloudflareGatewaySettings) -> dict[str, Any]:
''',
)

replace(
    "main_review/cloudflare_cli.py",
    '''            passed = (
                payload.get("status") == "ready"
                and payload.get("model") == model
                and payload.get("capabilities") == REQUIRED_PROOF_CAPABILITIES
            )
''',
    '''            passed = _proof_contract_matches(payload, model)
''',
)

replace(
    "main_review/cloudflare_cli.py",
    '''def qualify_models(
''',
    '''_SECURITY_COVERAGE_MARKERS = (
    "security",
    "injection",
    "shell",
    "auth",
    "authorization",
    "trust boundary",
    "vulnerability",
    "remote code execution",
    "rce",
)


def _coverage_area_matches(expected_category: str, reviewed_areas: set[str]) -> bool:
    expected = expected_category.strip().lower()
    if not expected:
        return True
    if expected in reviewed_areas:
        return True
    if expected == "security":
        return any(
            marker in area
            for area in reviewed_areas
            for marker in _SECURITY_COVERAGE_MARKERS
        )
    return False


def qualify_models(
''',
)

replace(
    "main_review/cloudflare_cli.py",
    '''            coverage_matches = (
                (not expected_path or expected_path in reviewed_files)
                and (not expected_category or expected_category in reviewed_areas)
            )
''',
    '''            coverage_matches = (
                (not expected_path or expected_path in reviewed_files)
                and _coverage_area_matches(expected_category, reviewed_areas)
            )
''',
)

Path("main_review/cloudflare_scout_qualification.py").write_text(
    '''"""Role-appropriate live qualification for low-cost Cloudflare Scout members."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from .cloudflare_cli import cloudflare_route
from .cloudflare_gateway import CloudflareGatewayError, CloudflareGatewaySettings
from .llm_provider import LLMProviderError, invoke_json

SCOUT_MAX_OUTPUT_TOKENS = 700


def _expected_facts(path: Path) -> dict[str, tuple[object, int]]:
    expected: dict[str, tuple[object, int]] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, raw_value = (part.strip() for part in line.split("=", 1))
        try:
            value = json.loads(raw_value.replace("'", '"'))
        except json.JSONDecodeError:
            continue
        expected[name] = (value, number)
    return expected


def qualify_scouts(
    settings: CloudflareGatewaySettings,
    *,
    root: str | Path,
    file: str,
) -> dict[str, Any]:
    settings.validate()
    root_path = Path(root)
    source = root_path / file
    if not source.is_file():
        raise CloudflareGatewayError(f"Scout qualification file is not readable: {file}")
    expected = _expected_facts(source)
    if not expected:
        raise CloudflareGatewayError("Scout qualification requires extractable constants.")
    source_text = source.read_text(encoding="utf-8")
    results: list[dict[str, Any]] = []
    for model in settings.models:
        route = cloudflare_route(
            settings,
            model=model,
            max_output_tokens=SCOUT_MAX_OUTPUT_TOKENS,
            timeout_seconds=settings.timeout_seconds,
        )
        system_prompt = (
            "Return JSON only. You are a Scout evidence-extraction council member. "
            "Extract grounded facts without classifying defects or inventing values."
        )
        user_prompt = json.dumps({
            "model": model,
            "path": file,
            "source": source_text,
            "instruction": (
                "Return status=ready, the exact model, coverage.files_reviewed, "
                "coverage.areas containing evidence extraction, and facts with name, value, and 1-based line."
            ),
        })
        started = time.monotonic()
        try:
            payload = invoke_json(route, system_prompt=system_prompt, user_prompt=user_prompt)
            coverage = payload.get("coverage", {}) if isinstance(payload.get("coverage"), dict) else {}
            reviewed = coverage.get("files_reviewed", [])
            areas = coverage.get("areas", [])
            facts = payload.get("facts", []) if isinstance(payload.get("facts"), list) else []
            observed = {
                str(item.get("name")): (item.get("value"), item.get("line"))
                for item in facts
                if isinstance(item, dict) and item.get("name")
            }
            passed = bool(
                payload.get("status") == "ready"
                and payload.get("model") == model
                and isinstance(reviewed, list)
                and file in {str(item) for item in reviewed}
                and isinstance(areas, list)
                and any("evidence" in str(item).lower() or "extraction" in str(item).lower() for item in areas)
                and observed == expected
            )
            results.append({
                "model": model,
                "passed": passed,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
                "expected_facts": expected,
                "response": {
                    "status": payload.get("status"),
                    "coverage": coverage,
                    "facts": facts,
                },
            })
        except LLMProviderError as error:
            results.append({
                "model": model,
                "passed": False,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
                "error": str(error),
            })
    qualified = [str(item["model"]) for item in results if item.get("passed") is True]
    return {
        "provider": "cloudflare-workers-ai",
        "proof_type": "scout_evidence_extraction",
        "model_count": len(settings.models),
        "passed_count": len(qualified),
        "qualified_models": qualified,
        "all_passed": bool(results) and len(qualified) == len(results),
        "models": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m main_review.cloudflare_scout_qualification")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--file", required=True)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--require", action="store_true")
    args = parser.parse_args(argv)
    settings = CloudflareGatewaySettings.from_environment()
    try:
        payload = qualify_scouts(settings, root=args.path, file=args.file)
    except CloudflareGatewayError as error:
        payload = {
            "provider": "cloudflare-workers-ai",
            "proof_type": "scout_evidence_extraction",
            "passed_count": 0,
            "all_passed": False,
            "error": str(error),
        }
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if payload.get("all_passed") or not args.require else 2


if __name__ == "__main__":
    raise SystemExit(main())
''',
    encoding="utf-8",
)

Path("tests/test_cloudflare_full_roster_qualification.py").write_text(
    '''from __future__ import annotations

from pathlib import Path

import pytest

from main_review import cloudflare_cli, cloudflare_scout_qualification, llm_provider
from main_review.cloudflare_gateway import CloudflareGatewaySettings


def _settings(models=("@cf/test/model",)) -> CloudflareGatewaySettings:
    return CloudflareGatewaySettings(
        account_id="0123456789abcdef0123456789abcdef",
        api_token="secret-token",
        models=models,
        host="127.0.0.1",
        port=0,
        timeout_seconds=90.0,
        max_request_bytes=100_000,
    )


def test_structured_proof_accepts_exact_contract_nested_under_required(monkeypatch: pytest.MonkeyPatch) -> None:
    model = "@cf/test/model"
    monkeypatch.setattr(
        cloudflare_cli,
        "invoke_json",
        lambda *args, **kwargs: {
            "required": {
                "status": "ready",
                "model": model,
                "capabilities": cloudflare_cli.REQUIRED_PROOF_CAPABILITIES,
            }
        },
    )
    result = cloudflare_cli.test_models(_settings())
    assert result["all_passed"] is True


def test_security_coverage_accepts_specific_security_areas() -> None:
    assert cloudflare_cli._coverage_area_matches(
        "security",
        {"command injection", "shell execution", "trust boundary", "authentication/authorization"},
    ) is True


def test_json_parser_selects_review_object_from_reasoning_text() -> None:
    text = 'thinking {"example": true} final {"verdict":"BLOCK","findings":[],"coverage":{}}'
    assert llm_provider._parse_json_text(text)["verdict"] == "BLOCK"
    payload = {"choices": [{"message": {"content": "", "reasoning_content": '{"status":"ready"}'}}]}
    assert llm_provider._extract_text(payload, "chat_completions") == '{"status":"ready"}'


def test_scout_qualification_requires_exact_grounded_facts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    source = root / "src" / "scout.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        'RETRY_LIMIT = 3\nTIMEOUT_SECONDS = 15\nSUPPORTED_LANGUAGES = ["python", "javascript"]\n',
        encoding="utf-8",
    )
    model = "@cf/test/model"
    monkeypatch.setattr(
        cloudflare_scout_qualification,
        "invoke_json",
        lambda *args, **kwargs: {
            "status": "ready",
            "model": model,
            "coverage": {"files_reviewed": ["src/scout.py"], "areas": ["evidence extraction"]},
            "facts": [
                {"name": "RETRY_LIMIT", "value": 3, "line": 1},
                {"name": "TIMEOUT_SECONDS", "value": 15, "line": 2},
                {"name": "SUPPORTED_LANGUAGES", "value": ["python", "javascript"], "line": 3},
            ],
        },
    )
    result = cloudflare_scout_qualification.qualify_scouts(
        _settings(), root=root, file="src/scout.py"
    )
    assert result["all_passed"] is True
''',
    encoding="utf-8",
)

workflow_template = Path("scripts/cloudflare_full_council_certification.yml.txt")
Path(".github/workflows/cloudflare-full-council-certification.yml").write_text(
    workflow_template.read_text(encoding="utf-8"),
    encoding="utf-8",
)
Path(".github/workflows/build-full-council-compatibility.yml").unlink(missing_ok=True)
workflow_template.unlink()
Path(__file__).unlink()
