"""Quota-safe, resumable certification for Sergeant's Cloudflare council roster."""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cloudflare_cli import qualify_models
from .cloudflare_gateway import CloudflareGatewayError, CloudflareGatewaySettings
from .cloudflare_scout_qualification import qualify_scouts
from .cloudflare_usage import cloudflare_usage_status
from .llm_provider import is_cloudflare_quota_error

CERTIFICATION_SCHEMA = "sergeant.cloudflare-incremental-certification.v1"
CONTRACT_VERSION = "role-mission-v3"
GRANITE_MODEL = "@cf/ibm-granite/granite-4.0-h-micro"

# Low-cost and routine members go first. Rare high-cost examiners are only called
# after the cheaper evidence lanes have completed and local budget remains.
CERTIFICATION_ORDER = (
    GRANITE_MODEL,
    "@cf/qwen/qwen3-30b-a3b-fp8",
    "@cf/zai-org/glm-4.7-flash",
    "@cf/openai/gpt-oss-20b",
    "@cf/openai/gpt-oss-120b",
    "@cf/qwen/qwen2.5-coder-32b-instruct",
    "@cf/moonshotai/kimi-k2.7-code",
)


def _utc_day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _fresh_ledger(tested_sha: str) -> dict[str, Any]:
    return {
        "schema_version": CERTIFICATION_SCHEMA,
        "contract_version": CONTRACT_VERSION,
        "tested_sha": tested_sha,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "quota_blocked_day": "",
        "budget_blocked": False,
        "budget_blocked_day": "",
        "members": {},
    }


def load_ledger(path: Path, tested_sha: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _fresh_ledger(tested_sha)
    if not isinstance(payload, dict):
        return _fresh_ledger(tested_sha)
    if (
        payload.get("schema_version") != CERTIFICATION_SCHEMA
        or payload.get("contract_version") != CONTRACT_VERSION
        or payload.get("tested_sha") != tested_sha
    ):
        return _fresh_ledger(tested_sha)
    members = payload.get("members")
    if not isinstance(members, dict):
        payload["members"] = {}
    today = _utc_day()
    if payload.get("quota_blocked_day") and payload.get("quota_blocked_day") != today:
        payload["quota_blocked_day"] = ""
    budget_day = str(payload.get("budget_blocked_day") or "")
    if payload.get("budget_blocked") is True and budget_day != today:
        payload["budget_blocked"] = False
        payload["budget_blocked_day"] = ""
    return payload


def save_ledger(path: Path, ledger: dict[str, Any]) -> None:
    ledger["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(path)


def _safe_error(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if is_cloudflare_quota_error(RuntimeError(text)):
        return "http_429_code_4006_daily_allocation"
    status = re.search(r"\bHTTP\s+(\d{3})\b", text, flags=re.IGNORECASE)
    if status:
        return f"http_{status.group(1)}"
    lowered = text.lower()
    if "blocked before inference" in lowered:
        return "local_budget_blocked"
    if "timeout" in lowered or "timed out" in lowered:
        return "timeout"
    if "parseable json" in lowered or "response" in lowered:
        return "response_contract"
    return "provider_error"


def _single_model_settings(settings: CloudflareGatewaySettings, model: str) -> CloudflareGatewaySettings:
    return replace(settings, models=(model,))


def _member_result(payload: dict[str, Any], model: str) -> dict[str, Any]:
    rows = payload.get("models", [])
    row = next(
        (
            item
            for item in rows
            if isinstance(item, dict) and str(item.get("model") or "") == model
        ),
        {},
    )
    error_kind = _safe_error(row.get("error"))
    transport_passed = bool(row and not error_kind and isinstance(row.get("response"), dict))
    role_passed = row.get("passed") is True
    return {
        "model": model,
        "status": "certified" if transport_passed and role_passed else "failed",
        "structured_transport_passed": transport_passed,
        "role_mission_passed": role_passed,
        "proof_type": str(payload.get("proof_type") or "role_mission"),
        "duration_ms": row.get("duration_ms"),
        "error_kind": error_kind,
        "response": row.get("response") if isinstance(row.get("response"), dict) else None,
        "tested_at": datetime.now(timezone.utc).isoformat(),
    }


def _run_member(
    settings: CloudflareGatewaySettings,
    *,
    model: str,
    root: Path,
    auth_file: str,
    scout_file: str,
) -> dict[str, Any]:
    selected = _single_model_settings(settings, model)
    if model == GRANITE_MODEL:
        payload = qualify_scouts(selected, root=root, file=scout_file)
    else:
        payload = qualify_models(
            selected,
            root=root,
            changed_files=[auth_file],
            expected_verdict="BLOCK",
            expected_path=auth_file,
            expected_category="security",
            expected_severity="blocker",
            expected_evidence="shell=True",
        )
    return _member_result(payload, model)


def certify_incrementally(
    settings: CloudflareGatewaySettings,
    *,
    root: Path,
    auth_file: str,
    scout_file: str,
    tested_sha: str,
    ledger_path: Path,
) -> dict[str, Any]:
    settings.validate()
    expected = [model for model in CERTIFICATION_ORDER if model in settings.models]
    for model in settings.models:
        if model not in expected:
            expected.append(model)
    ledger = load_ledger(ledger_path, tested_sha)
    members = ledger.setdefault("members", {})
    called_models: list[str] = []
    skipped_models: list[str] = []
    stopped_reason = ""
    today = _utc_day()

    if ledger.get("quota_blocked_day") == today:
        stopped_reason = "quota_blocked_until_next_utc_day"
    elif ledger.get("budget_blocked") is True and ledger.get("budget_blocked_day") == today:
        stopped_reason = "local_budget_blocked"
    else:
        for model in expected:
            existing = members.get(model)
            if isinstance(existing, dict) and existing.get("status") == "certified":
                skipped_models.append(model)
                continue
            result = _run_member(
                settings,
                model=model,
                root=root,
                auth_file=auth_file,
                scout_file=scout_file,
            )
            members[model] = result
            called_models.append(model)
            if result.get("error_kind") == "http_429_code_4006_daily_allocation":
                ledger["quota_blocked_day"] = today
                result["status"] = "quota_blocked"
                stopped_reason = "quota_blocked_until_next_utc_day"
                save_ledger(ledger_path, ledger)
                break
            if result.get("error_kind") == "local_budget_blocked":
                ledger["budget_blocked"] = True
                ledger["budget_blocked_day"] = today
                result["status"] = "budget_blocked"
                stopped_reason = "local_budget_blocked"
                save_ledger(ledger_path, ledger)
                break
            save_ledger(ledger_path, ledger)

    certified = [
        model
        for model in expected
        if isinstance(members.get(model), dict)
        and members[model].get("status") == "certified"
    ]
    pending = [model for model in expected if model not in certified]
    usage = cloudflare_usage_status()
    summary = {
        "schema_version": CERTIFICATION_SCHEMA,
        "contract_version": CONTRACT_VERSION,
        "tested_sha": tested_sha,
        "expected_member_count": len(expected),
        "certified_member_count": len(certified),
        "certified_models": certified,
        "pending_models": pending,
        "called_models": called_models,
        "skipped_models": skipped_models,
        "stopped_reason": stopped_reason,
        "quota_blocked": ledger.get("quota_blocked_day") == today,
        "budget_blocked": (
            ledger.get("budget_blocked") is True
            and ledger.get("budget_blocked_day") == today
        ),
        "passed": bool(expected) and len(certified) == len(expected),
        "members": [members.get(model, {"model": model, "status": "pending"}) for model in expected],
        "usage": {
            key: usage.get(key)
            for key in (
                "schema_version",
                "day",
                "reserved_neurons",
                "request_count",
                "quota_blocked",
                "reset_at",
                "daily_limit_neurons",
                "safety_reserve_neurons",
                "usable_limit_neurons",
                "remaining_reserved_capacity_neurons",
            )
        },
    }
    save_ledger(ledger_path, ledger)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m main_review.cloudflare_incremental_certification")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--auth-file", required=True)
    parser.add_argument("--scout-file", required=True)
    parser.add_argument("--tested-sha", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--require", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = certify_incrementally(
            CloudflareGatewaySettings.from_environment(),
            root=Path(args.path),
            auth_file=args.auth_file,
            scout_file=args.scout_file,
            tested_sha=args.tested_sha,
            ledger_path=Path(args.ledger),
        )
    except CloudflareGatewayError as error:
        payload = {
            "schema_version": CERTIFICATION_SCHEMA,
            "tested_sha": args.tested_sha,
            "passed": False,
            "error": str(error),
        }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if payload.get("passed") or not args.require else 2


if __name__ == "__main__":
    raise SystemExit(main())
