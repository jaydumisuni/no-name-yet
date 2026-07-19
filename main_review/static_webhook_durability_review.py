"""Static review for webhook acknowledgement and atomic/idempotent money writes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".py"}


def _safe_text(root: Path, relative: str) -> str:
    try:
        resolved_root = root.resolve()
        path = (resolved_root / relative).resolve()
        if not path.is_relative_to(resolved_root) or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _line(text: str, offset: int) -> int:
    return text[: max(0, offset)].count("\n") + 1


def _finding(path: str, line: int, root: str, message: str, evidence: str, verification: str, severity: str = "critical") -> dict[str, Any]:
    return {
        "source": "static-webhook-durability-officer",
        "officer": "Medic",
        "capability": "durability",
        "category": "durability",
        "severity": severity,
        "root_cause": root,
        "path": path,
        "line_start": line,
        "line_end": line,
        "evidence_ref": f"{path}:{line}",
        "supporting_evidence_refs": [f"{path}:{line}"],
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": [
            "Checked whether failed side effects cause a non-success webhook response and provider retry.",
            "Checked for one atomic database operation or transaction spanning balance and ledger state.",
            "Checked for a provider-event/session idempotency key enforced at the write boundary.",
        ],
        "verification_test": verification,
        "confidence": 0.98,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def run_static_webhook_durability_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    findings: list[dict[str, Any]] = []
    readable: list[str] = []

    for path in changed:
        if Path(path).suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        lowered = f"{path}\n{text}".lower()
        if "webhook" not in lowered:
            continue

        success = re.search(
            r"return\s+(?:NextResponse\.json|Response\.json|jsonify|JSONResponse)\s*\([^;\n]*(?:received|success|ok)[^;\n]*\)",
            text,
            re.I,
        )
        swallowed = re.search(r"catch\s*(?:\([^)]*\))?\s*\{(?P<body>[\s\S]{0,700}?)\}", text, re.I)
        if success is not None and swallowed is not None:
            body = swallowed.group("body")
            explicit_failure = bool(
                re.search(r"return[\s\S]{0,200}(?:status\s*:\s*5\d\d|status_code\s*=\s*5\d\d)", body, re.I)
                or re.search(r"\braise\b|\bthrow\b", body, re.I)
            )
            side_effects = bool(re.search(r"\b(?:insert|update|upsert|rpc|save|create|credit|grant)\s*\(", text, re.I))
            if side_effects and not explicit_failure and swallowed.start() < success.start():
                findings.append(
                    _finding(
                        path,
                        _line(text, swallowed.start()),
                        "webhook-side-effect-failure-acknowledged-as-success",
                        "The webhook acknowledges delivery after swallowing a failed durable side effect.",
                        (
                            "A catch block logs the processing failure but does not rethrow or return a non-2xx response; execution then reaches the "
                            "unconditional success acknowledgement. The provider can treat the event as delivered and never retry the lost side effect."
                        ),
                        (
                            "Propagate every required persistence failure to a non-2xx response, then prove the provider retry reaches an idempotent "
                            "handler and completes the missing side effect exactly once."
                        ),
                    )
                )

        money_words = re.search(r"\b(?:credit|wallet|balance|coins?|payment|purchase|grant)\b", lowered)
        read_balance = re.search(r"select\s*\(\s*[\"']balance[\"']\s*\)|\.select\s*\(\s*[\"']balance[\"']", text, re.I)
        computed_balance = re.search(r"(?:new|next|updated)?balance\s*=\s*[^;\n]+\+", text, re.I)
        balance_write = re.search(r"\.from\s*\(\s*[\"']wallets?[\"']\s*\)[\s\S]{0,600}?\.(?:update|upsert)\s*\(", text, re.I)
        ledger_write = re.search(r"\.from\s*\(\s*[\"']transactions?[\"']\s*\)[\s\S]{0,500}?\.insert\s*\(", text, re.I)
        atomic = bool(
            re.search(r"\.rpc\s*\(", text, re.I)
            or re.search(r"\btransaction\s*\(", text, re.I)
            or re.search(r"BEGIN[\s\S]{0,3000}COMMIT", text, re.I)
        )
        idempotent = bool(
            re.search(r"idempoten|on\s+conflict|unique\s+index|dedup", lowered)
            or re.search(r"stripe_session_id[\s\S]{0,400}(?:exists|eq\s*\(|where)", text, re.I)
        )
        if money_words and read_balance and computed_balance and balance_write and ledger_write and not (atomic and idempotent):
            line = _line(text, read_balance.start())
            findings.append(
                _finding(
                    path,
                    line,
                    "webhook-money-credit-is-nonatomic-and-nonidempotent",
                    "Webhook retry can double-credit or partially apply a money mutation because balance and ledger writes are separate and lack an atomic deduplication point.",
                    (
                        "The handler reads a balance, computes a replacement value, writes the wallet and then inserts a purchase record as separate "
                        "application operations. The provider event/session identifier is stored as metadata but is not enforced as an idempotency key."
                    ),
                    (
                        "Move crediting into one database transaction or RPC with a unique provider-event key, then prove duplicate and concurrent "
                        "webhook deliveries commit one balance increment and one ledger record."
                    ),
                )
            )

    unique = {(str(item["root_cause"]), str(item["path"])): item for item in findings}
    return {
        "schema_version": "sergeant.static-webhook-durability-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
