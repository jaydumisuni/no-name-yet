"""CLI for connecting Sergeant Cpl to Cloudflare Workers AI."""
from __future__ import annotations

import argparse
import json
import shlex
import time
from pathlib import Path
from typing import Any

from .cloudflare_models import (
    DEFAULT_MODEL_PROOF_OUTPUT_TOKENS,
    model_proof_output_tokens,
)
from .cloudflare_gateway import (
    CloudflareGatewayError,
    CloudflareGatewaySettings,
    build_server,
)
from .cpl_council import findings_match
from .cpl_runtime import run_cpl_review
from .diff_review import parse_changed_files_text
from .llm_provider import LLMProviderError, LLMRoute, LLMSettings, invoke_json

REQUIRED_PROOF_CAPABILITIES = ["structured_json", "reasoning"]
VALID_COUNCIL_VERDICTS = {"PASS", "NEEDS WORK", "BLOCK"}
MODEL_PROOF_MAX_OUTPUT_TOKENS = DEFAULT_MODEL_PROOF_OUTPUT_TOKENS
COUNCIL_PROOF_MAX_OUTPUT_TOKENS = 1200


def cloudflare_route(
    settings: CloudflareGatewaySettings,
    *,
    model: str | None = None,
    max_output_tokens: int = COUNCIL_PROOF_MAX_OUTPUT_TOKENS,
) -> LLMRoute:
    settings.validate()
    selected = model or settings.models[0]
    if selected not in settings.models:
        raise CloudflareGatewayError(f"Model is not in the configured Cloudflare roster: {selected!r}")
    return LLMRoute(
        provider="cloudflare-workers-ai",
        base_url=f"https://api.cloudflare.com/client/v4/accounts/{settings.account_id}/ai/v1",
        model=selected,
        protocol="chat_completions",
        api_key=settings.api_token,
        timeout_seconds=settings.timeout_seconds,
        max_output_tokens=max_output_tokens,
        discovered_models=settings.models,
    )


def _print(payload: object, *, pretty: bool) -> None:
    print(json.dumps(payload, indent=2 if pretty else None, sort_keys=True))


def _proof_prompt(model: str) -> tuple[str, str]:
    return (
        "Return JSON only. You are proving that a model route can follow a structured Sergeant contract.",
        json.dumps(
            {
                "instruction": "Return the exact requested JSON fields without Markdown.",
                "model": model,
                "required": {
                    "status": "ready",
                    "model": model,
                    "capabilities": REQUIRED_PROOF_CAPABILITIES,
                },
            }
        ),
    )


def test_models(settings: CloudflareGatewaySettings) -> dict[str, Any]:
    settings.validate()
    results: list[dict[str, Any]] = []
    for model in settings.models:
        proof_tokens = model_proof_output_tokens(model)
        route = cloudflare_route(
            settings,
            model=model,
            max_output_tokens=proof_tokens,
        )
        system_prompt, user_prompt = _proof_prompt(model)
        started = time.monotonic()
        try:
            payload = invoke_json(route, system_prompt=system_prompt, user_prompt=user_prompt)
            passed = (
                payload.get("status") == "ready"
                and payload.get("model") == model
                and payload.get("capabilities") == REQUIRED_PROOF_CAPABILITIES
            )
            results.append(
                {
                    "model": model,
                    "passed": passed,
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                    "max_output_tokens": proof_tokens,
                    "response": payload,
                }
            )
        except LLMProviderError as error:
            results.append(
                {
                    "model": model,
                    "passed": False,
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                    "max_output_tokens": proof_tokens,
                    "error": str(error),
                }
            )
    return {
        "provider": "cloudflare-workers-ai",
        "model_count": len(settings.models),
        "passed_count": sum(bool(item.get("passed")) for item in results),
        "all_passed": bool(results) and all(bool(item.get("passed")) for item in results),
        "models": results,
    }


def _changed_files(value: str, file_list: str | None) -> list[str]:
    if file_list:
        return parse_changed_files_text(Path(file_list).read_text(encoding="utf-8"))
    return parse_changed_files_text(value)


def _candidate_meets_expected_contract(
    candidate: dict[str, Any],
    *,
    expected_category: str,
    expected_severity: str,
    expected_evidence: str,
) -> bool:
    if expected_category and str(candidate.get("category") or "").lower() != expected_category:
        return False
    if expected_severity and str(candidate.get("severity") or "").lower() != expected_severity:
        return False
    if expected_evidence:
        evidence = str(candidate.get("evidence") or "").lower()
        if candidate.get("evidence_verified") is not True or expected_evidence not in evidence:
            return False
    return True


def _completed_matching_models(
    finding: dict[str, Any],
    passes: list[dict[str, Any]],
    *,
    expected_category: str,
    expected_severity: str,
    expected_evidence: str,
) -> list[str]:
    return sorted({
        str(report.get("model"))
        for report in passes
        if report.get("model")
        and any(
            findings_match(finding, candidate)
            and _candidate_meets_expected_contract(
                candidate,
                expected_category=expected_category,
                expected_severity=expected_severity,
                expected_evidence=expected_evidence,
            )
            for candidate in report.get("findings", [])
        )
    })


def _expected_finding_result(
    findings: list[dict[str, Any]],
    passes: list[dict[str, Any]],
    *,
    expected_path: str,
    expected_category: str,
    expected_severity: str,
    expected_evidence: str,
    minimum_supporting_models: int,
) -> dict[str, Any]:
    expected_path = expected_path.strip()
    expected_category = expected_category.strip().lower()
    expected_severity = expected_severity.strip().lower()
    expected_evidence = expected_evidence.strip().lower()
    required = bool(expected_path or expected_category or expected_severity or expected_evidence)
    matches: list[dict[str, Any]] = []
    for finding in findings:
        if expected_path and str(finding.get("path") or "") != expected_path:
            continue
        if expected_category and str(finding.get("category") or "").lower() != expected_category:
            continue
        if expected_severity and str(finding.get("severity") or "").lower() != expected_severity:
            continue
        evidence = str(finding.get("evidence") or "").lower()
        if expected_evidence and (
            finding.get("evidence_verified") is not True
            or expected_evidence not in evidence
        ):
            continue
        models = _completed_matching_models(
            finding,
            passes,
            expected_category=expected_category,
            expected_severity=expected_severity,
            expected_evidence=expected_evidence,
        )
        matches.append({
            "path": finding.get("path"),
            "category": finding.get("category"),
            "severity": finding.get("severity"),
            "message": finding.get("message"),
            "supporting_models": models,
            "support_count": len(models),
        })
    passed = (not required) or any(
        int(item.get("support_count", 0)) >= minimum_supporting_models for item in matches
    )
    return {
        "required": required,
        "passed": passed,
        "expected_path": expected_path,
        "expected_category": expected_category,
        "expected_severity": expected_severity,
        "expected_evidence": expected_evidence,
        "minimum_supporting_models": minimum_supporting_models,
        "matches": matches,
    }


def run_council_proof(
    settings: CloudflareGatewaySettings,
    *,
    root: str | Path,
    changed_files: list[str],
    expected_verdict: str = "",
    expected_path: str = "",
    expected_category: str = "",
    expected_severity: str = "",
    expected_evidence: str = "",
    minimum_supporting_models: int = 1,
) -> dict[str, Any]:
    settings.validate()
    if len(settings.models) < 2:
        raise CloudflareGatewayError("Council proof requires at least two configured Cloudflare models.")
    context = {
        "proof_type": "cloudflare-live-council",
        "repository_root": str(Path(root).resolve()),
        "changed_files": changed_files,
        "rule": "This proof must report actual model members and must not infer independence from repeated calls to one model.",
    }
    llm_settings = LLMSettings(
        enabled=True,
        policy="required",
        provider="cloudflare-workers-ai",
        base_url=f"https://api.cloudflare.com/client/v4/accounts/{settings.account_id}/ai/v1",
        model=settings.models[0],
        protocol="chat_completions",
        api_key=settings.api_token,
        timeout_seconds=settings.timeout_seconds,
        max_output_tokens=COUNCIL_PROOF_MAX_OUTPUT_TOKENS,
    )
    result = run_cpl_review(
        root,
        changed_files,
        context,
        settings=llm_settings,
        route=cloudflare_route(
            settings,
            max_output_tokens=COUNCIL_PROOF_MAX_OUTPUT_TOKENS,
        ),
    )
    council = result.get("council", {}) if isinstance(result.get("council"), dict) else {}
    passes = [item for item in result.get("passes", []) if isinstance(item, dict)]
    distinct_models = sorted({str(item.get("model")) for item in passes if item.get("model")})
    errors = [str(item) for item in result.get("errors", []) if str(item).strip()]
    final_gaps = council.get("final_gaps", []) if isinstance(council.get("final_gaps"), list) else []
    verdict = str(result.get("verdict") or "")
    effective_findings = [
        item for item in council.get("effective_findings", []) if isinstance(item, dict)
    ]
    expected_result = _expected_finding_result(
        effective_findings,
        passes,
        expected_path=expected_path,
        expected_category=expected_category,
        expected_severity=expected_severity,
        expected_evidence=expected_evidence,
        minimum_supporting_models=max(1, minimum_supporting_models),
    )
    expected_verdict = expected_verdict.strip().upper()
    verdict_matches = not expected_verdict or verdict == expected_verdict
    passed = (
        result.get("status") == "completed"
        and verdict in VALID_COUNCIL_VERDICTS
        and verdict_matches
        and expected_result["passed"] is True
        and len(distinct_models) > 1
        and council.get("true_model_independence") is True
        and council.get("complete") is True
        and not errors
        and not final_gaps
    )
    return {
        "schema_version": "sergeant.cloudflare-council-proof.v1",
        "passed": passed,
        "provider": "cloudflare-workers-ai",
        "configured_models": list(settings.models),
        "distinct_models": distinct_models,
        "model_call_count": len(passes),
        "true_model_independence": council.get("true_model_independence", False),
        "council_complete": council.get("complete", False),
        "final_gaps": final_gaps,
        "status": result.get("status"),
        "verdict": verdict,
        "expected_verdict": expected_verdict,
        "verdict_matches": verdict_matches,
        "expected_finding": expected_result,
        "errors": errors,
        "council": council,
    }


def _gateway_environment(settings: CloudflareGatewaySettings) -> dict[str, str]:
    return {
        "SERGEANT_CPL_ENABLED": "true",
        "SERGEANT_CPL_POLICY": "required",
        "SERGEANT_CPL_PROVIDER": "configured",
        "SERGEANT_CPL_BASE_URL": f"http://{settings.host}:{settings.port}/v1",
        "SERGEANT_CPL_MODEL": settings.models[0],
        "SERGEANT_CPL_PROTOCOL": "chat_completions",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sergeant-cloudflare")
    parser.add_argument("--pretty", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Show Cloudflare configuration without revealing credentials.")
    status.add_argument("--require", action="store_true")

    env = sub.add_parser("env", help="Print the Sergeant environment required to use the local gateway.")
    env.add_argument("--shell", choices=["powershell", "bash", "json"], default="json")

    test = sub.add_parser("test-models", help="Call every configured Cloudflare model with a structured-output proof.")
    test.add_argument("--require", action="store_true")

    gateway = sub.add_parser("gateway", help="Run the local OpenAI-compatible Cloudflare gateway.")
    gateway.add_argument("--host")
    gateway.add_argument("--port", type=int)

    council = sub.add_parser("council-proof", help="Run a live multi-model Cpl proof through Cloudflare.")
    council.add_argument("path", nargs="?", default=".")
    source = council.add_mutually_exclusive_group(required=True)
    source.add_argument("--files", help="Comma/newline-separated changed files.")
    source.add_argument("--file-list", help="File containing changed paths.")
    council.add_argument("--expected-verdict", choices=sorted(VALID_COUNCIL_VERDICTS), default="")
    council.add_argument("--expected-path", default="")
    council.add_argument("--expected-category", default="")
    council.add_argument("--expected-severity", default="")
    council.add_argument("--expected-evidence", default="")
    council.add_argument("--minimum-supporting-models", type=int, default=1)
    council.add_argument("--output")
    council.add_argument("--no-fail", action="store_true")
    return parser


def _powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _render_shell(values: dict[str, str], shell: str) -> str:
    if shell == "json":
        return json.dumps(values, indent=2, sort_keys=True)
    if shell == "powershell":
        return "\n".join(f"$env:{key}={_powershell_quote(value)}" for key, value in values.items())
    return "\n".join(f"export {key}={shlex.quote(value)}" for key, value in values.items())


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = CloudflareGatewaySettings.from_environment(
        host=getattr(args, "host", None),
        port=getattr(args, "port", None),
    )

    if args.command == "status":
        payload = settings.public_dict()
        payload["valid"] = True
        try:
            settings.validate()
        except CloudflareGatewayError as error:
            payload["valid"] = False
            payload["error"] = str(error)
        _print(payload, pretty=args.pretty)
        return 0 if payload["valid"] or not args.require else 2

    if args.command == "env":
        settings.validate(require_credentials=False)
        print(_render_shell(_gateway_environment(settings), args.shell))
        return 0

    if args.command == "test-models":
        try:
            payload = test_models(settings)
        except CloudflareGatewayError as error:
            payload = {"provider": "cloudflare-workers-ai", "all_passed": False, "error": str(error)}
        _print(payload, pretty=args.pretty)
        return 0 if payload.get("all_passed") or not args.require else 2

    if args.command == "gateway":
        try:
            server = build_server(settings)
        except CloudflareGatewayError as error:
            parser.error(str(error))
        print(json.dumps({"status": "ready", **settings.public_dict()}, indent=2 if args.pretty else None))
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0

    if args.command == "council-proof":
        changed = _changed_files(args.files or "", args.file_list)
        if not changed:
            parser.error("At least one changed file is required.")
        try:
            payload = run_council_proof(
                settings,
                root=args.path,
                changed_files=changed,
                expected_verdict=args.expected_verdict,
                expected_path=args.expected_path,
                expected_category=args.expected_category,
                expected_severity=args.expected_severity,
                expected_evidence=args.expected_evidence,
                minimum_supporting_models=max(1, args.minimum_supporting_models),
            )
        except CloudflareGatewayError as error:
            payload = {"schema_version": "sergeant.cloudflare-council-proof.v1", "passed": False, "error": str(error)}
        text = json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True) + "\n"
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text, encoding="utf-8")
        print(text, end="")
        return 0 if payload.get("passed") or args.no_fail else 2

    parser.error("Unsupported command.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
