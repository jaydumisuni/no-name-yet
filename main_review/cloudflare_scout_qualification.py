"""Role-appropriate live qualification for low-cost Cloudflare Scout members."""
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


def _contained_source(root: str | Path, file: str) -> Path:
    """Resolve a Scout fixture while preventing absolute or parent-path escape."""

    root_path = Path(root).resolve()
    requested = Path(file)
    if requested.is_absolute():
        raise CloudflareGatewayError(
            f"Scout qualification file must remain inside the repository: {file}"
        )
    source = (root_path / requested).resolve()
    try:
        source.relative_to(root_path)
    except ValueError as error:
        raise CloudflareGatewayError(
            f"Scout qualification file must remain inside the repository: {file}"
        ) from error
    return source


def qualify_scouts(
    settings: CloudflareGatewaySettings,
    *,
    root: str | Path,
    file: str,
) -> dict[str, Any]:
    settings.validate()
    source = _contained_source(root, file)
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
