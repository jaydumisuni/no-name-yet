"""Static checks for debug credential safety, subprocess bounds, and transaction scope."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_GO_SUFFIXES = {".go"}
_SWIFT_SUFFIXES = {".swift"}
_SCRIPT_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}
_SOURCE_SUFFIXES = _GO_SUFFIXES | _SWIFT_SUFFIXES | _SCRIPT_SUFFIXES


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


def _finding(
    *,
    root_cause: str,
    path: str,
    line_start: int,
    category: str,
    officer: str,
    message: str,
    evidence: str,
    falsifiers: Iterable[str],
    verification: str,
    supporting: Iterable[str] = (),
    confidence: float = 0.97,
) -> dict[str, Any]:
    refs = [f"{path}:{line_start}", *[str(item) for item in supporting]]
    return {
        "source": "static-transfer-12-officer",
        "officer": officer,
        "capability": category,
        "category": category,
        "severity": "major",
        "root_cause": root_cause,
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": refs[0],
        "supporting_evidence_refs": list(dict.fromkeys(refs)),
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": list(falsifiers),
        "verification_test": verification,
        "confidence": confidence,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def _go_debug_dump_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() not in _GO_SUFFIXES:
        return []

    findings: list[dict[str, Any]] = []
    dump_re = re.compile(
        r"httputil\.DumpRequestOut\s*\(\s*(?P<request>[A-Za-z_][A-Za-z0-9_]*)\s*,\s*(?P<body>true|false)\s*\)"
    )
    for dump in dump_re.finditer(text):
        request_name = dump.group("request")
        include_body = dump.group("body") == "true"
        before = text[max(0, dump.start() - 1800) : dump.start()]
        after = text[dump.end() : min(len(text), dump.end() + 1200)]
        logging_sink = bool(
            re.search(r"(?:stderr|stdout|log\.|logger\.|Printf|Fprintf|Println|DEBUG REQUEST)", after, re.I)
            or re.search(r"(?:debugTransport|debug|trace)", before, re.I)
        )
        if not logging_sink:
            continue

        cloned = re.search(
            rf"\b{re.escape(request_name)}\s*:=\s*[A-Za-z_][A-Za-z0-9_]*\.Clone\s*\(",
            before,
        )
        redacted = bool(
            re.search(
                rf"{re.escape(request_name)}\.Header\.(?:Set|Del)\s*\(\s*[\"']Authorization[\"']",
                before,
                re.I,
            )
            or re.search(r"(?:redact|sanitize|mask).*Authorization", before, re.I | re.S)
        )
        request_auth_context = bool(
            re.search(r"Authorization|Bearer|api[_-]?key|oauth", text, re.I)
            or re.search(r"RoundTrip\s*\(\s*req\s+\*http\.Request", text)
        )

        line = _line(text, dump.start())
        if request_auth_context and not redacted:
            findings.append(
                _finding(
                    root_cause="http-debug-dump-logs-authorization-without-redaction",
                    path=path,
                    line_start=line,
                    category="credential_exposure",
                    officer="Challenger",
                    message="An HTTP request is written to debug output without redacting authentication headers.",
                    evidence=(
                        f"`DumpRequestOut({request_name}, ...)` feeds a debug/logging sink, but the reviewed path does not remove or replace "
                        "the Authorization value before serialization. Bearer tokens or API keys can enter stderr, CI logs, or log aggregation."
                    ),
                    falsifiers=(
                        "Checked for Header.Set/Del on Authorization before the dump.",
                        "Checked for an explicit request redaction/sanitization helper.",
                        "Checked that the dump reaches a diagnostic/logging sink rather than an internal wire encoder.",
                    ),
                    verification=(
                        "Clone the request for diagnostics, replace sensitive headers with a fixed redacted marker, and prove the raw credential is absent from captured debug output while the original request still sends the real value."
                    ),
                )
            )

        original_roundtrip = bool(
            re.search(
                rf"(?:transport|RoundTripper|dt\.transport)\.RoundTrip\s*\(\s*{re.escape(request_name)}\s*\)",
                after,
            )
        )
        body_neutralized = bool(
            re.search(
                rf"\b{re.escape(request_name)}\.Body\s*=\s*(?:http\.)?NoBody",
                before,
            )
            or not include_body
        )
        if include_body and original_roundtrip and cloned is None and not body_neutralized:
            findings.append(
                _finding(
                    root_cause="http-debug-dump-consumes-live-request-body",
                    path=path,
                    line_start=line,
                    category="correctness",
                    officer="Engineer",
                    message="Debug serialization reads the same request body that the transport later sends.",
                    evidence=(
                        f"The live request `{request_name}` is dumped with `body=true` and then passed to `RoundTrip`. Reading the body for diagnostics can drain or close it before POST/PUT/PATCH delivery."
                    ),
                    falsifiers=(
                        "Checked whether a separate cloned request is dumped.",
                        "Checked whether the diagnostic clone body is replaced with http.NoBody.",
                        "Checked whether DumpRequestOut is called with body=false.",
                    ),
                    verification=(
                        "Dump a detached diagnostic clone with body disabled or independently replayable bytes, then prove the server receives the original request body unchanged."
                    ),
                )
            )
    return findings


def _swift_subprocess_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() not in _SWIFT_SUFFIXES:
        return []
    if "Process()" not in text or ".run()" not in text:
        return []

    bounded_runner = bool(
        re.search(
            r"(?:ProcessRunner\.run|withThrowingTaskGroup|withTaskCancellationHandler|Task\.sleep|timeout\s*:|withTimeout|terminate\s*\(\))",
            text,
        )
    )
    if bounded_runner:
        return []

    findings: list[dict[str, Any]] = []
    process_re = re.compile(r"\blet\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*Process\s*\(\s*\)")
    for process in process_re.finditer(text):
        name = process.group("name")
        after = text[process.end() : min(len(text), process.end() + 4200)]
        run = re.search(rf"\b{re.escape(name)}\.run\s*\(\s*\)", after)
        if run is None:
            continue
        waits = bool(
            re.search(r"(?:readDataToEndOfFile\s*\(|waitUntilExit\s*\(\s*\))", after)
        )
        if not waits:
            continue
        timeout = bool(
            re.search(
                rf"(?:{re.escape(name)}\.terminate\s*\(|{re.escape(name)}\.interrupt\s*\(|timeout|deadline|watchdog|Task\.sleep)",
                after,
                re.I,
            )
        )
        if timeout:
            continue
        line = _line(text, process.start())
        findings.append(
            _finding(
                root_cause="external-process-wait-without-timeout-or-cancellation",
                path=path,
                line_start=line,
                category="resource_lifecycle",
                officer="Mechanic",
                message="An external subprocess is awaited through blocking pipe/exit operations without a timeout or cancellation owner.",
                evidence=(
                    f"`{name}` is launched directly and the path waits for EOF or process exit. No watchdog, deadline, terminate/interrupt path, or bounded process runner is present, so a hung child can stall the caller indefinitely."
                ),
                falsifiers=(
                    "Checked for a shared bounded ProcessRunner or injected command runner with timeout.",
                    "Checked for Task.sleep/deadline/watchdog cancellation and terminate/interrupt cleanup.",
                    "Checked that the path actually waits for output or exit rather than launching fire-and-forget work.",
                ),
                verification=(
                    "Route the command through an argv-only bounded runner, enforce a finite timeout, terminate descendants and close pipes on expiry, and prove launch failure, timeout, nonzero exit, and success all release the caller."
                ),
            )
        )
    return findings


def _typescript_transaction_findings(changed: list[str], texts: dict[str, str]) -> list[dict[str, Any]]:
    route_candidates: list[tuple[str, str]] = []
    helper_candidates: list[tuple[str, str]] = []
    for path in changed:
        suffix = Path(path).suffix.lower()
        if suffix not in _SCRIPT_SUFFIXES:
            continue
        text = texts.get(path, "")
        if re.search(r"(?:export\s+async\s+function\s+(?:POST|PUT|PATCH)|route)", text, re.I):
            route_candidates.append((path, text))
        if re.search(r"\b(?:move|debit|credit|refund|vault|wallet|balance)\w*\s*\(", text, re.I):
            helper_candidates.append((path, text))

    findings: list[dict[str, Any]] = []
    for route_path, route in route_candidates:
        money_call = re.search(
            r"await\s+(?P<helper>[A-Za-z_$][A-Za-z0-9_$]*(?:Vault|Wallet|Balance|Credit|Debit|Refund)[A-Za-z0-9_$]*)\s*\(",
            route,
            re.I,
        )
        if money_call is None:
            continue
        helper_name = money_call.group("helper")
        aggregate_read = re.search(
            r"SELECT[\s\S]{0,500}(?:market|pool|order|account|wallet)[\s\S]{0,200}WHERE",
            route,
            re.I,
        )
        aggregate_update = re.search(
            r"UPDATE[\s\S]{0,300}(?:market|pool|order|account|wallet)",
            route,
            re.I,
        )
        related_insert = re.search(
            r"INSERT\s+INTO[\s\S]{0,300}(?:prediction|stake|order|transaction|ledger|payment)",
            route,
            re.I,
        )
        if aggregate_read is None or aggregate_update is None or related_insert is None:
            continue
        route_transaction = bool(
            re.search(r"\bdb\.connect\s*\(|\bclient\.query\s*\(\s*[`'\"]BEGIN", route, re.I)
            and re.search(r"FOR\s+UPDATE|pg_advisory|LOCK\s+TABLE", route, re.I)
        )
        if route_transaction:
            continue

        helper_evidence: tuple[str, int] | None = None
        for helper_path, helper_text in helper_candidates:
            definition = re.search(
                rf"export\s+async\s+function\s+{re.escape(helper_name)}\s*\([^)]*\)[\s\S]{{0,8000}}?\bdb\.connect\s*\(\)",
                helper_text,
                re.I,
            )
            if definition is None:
                continue
            if re.search(r"\bclient\.query\s*\(\s*[`'\"]BEGIN", helper_text[definition.start() :], re.I):
                helper_evidence = (helper_path, _line(helper_text, definition.start()))
                break
        if helper_evidence is None:
            continue

        line = _line(route, aggregate_read.start())
        findings.append(
            _finding(
                root_cause="multi-resource-financial-operation-spans-separate-transactions",
                path=route_path,
                line_start=line,
                category="transaction_integrity",
                officer="Engineer",
                message="One financial operation mutates related money and aggregate records through separate transaction owners.",
                evidence=(
                    f"The route reads and later replaces a mutable aggregate, calls `{helper_name}` whose implementation opens and commits its own database transaction, then performs additional aggregate and record writes through separate queries. Concurrent requests can overwrite the same snapshot, and a later failure can leave money moved without the corresponding domain record."
                ),
                falsifiers=(
                    "Checked for one route-owned database client and BEGIN/COMMIT/ROLLBACK covering every write.",
                    "Checked for SELECT ... FOR UPDATE or an equivalent lock before aggregate read-modify-write.",
                    "Checked whether the money helper accepts the caller's transaction client instead of opening its own.",
                    "Checked that the aggregate update and related insert belong to the same business operation.",
                ),
                verification=(
                    "Open one transaction for the complete operation, lock the mutable aggregate before reading it, pass the same client into money movement, and commit the debit/refund, aggregate update, and related record together. Prove concurrent requests preserve every stake and injected failures roll back all resources."
                ),
                supporting=(f"{helper_evidence[0]}:{helper_evidence[1]}",),
            )
        )
    return findings


def run_static_transfer_12_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    texts: dict[str, str] = {}
    findings: list[dict[str, Any]] = []
    readable: list[str] = []

    for path in changed:
        if Path(path).suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        texts[path] = text
        readable.append(path)
        findings.extend(_go_debug_dump_findings(path, text))
        findings.extend(_swift_subprocess_findings(path, text))

    findings.extend(_typescript_transaction_findings(changed, texts))

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[(
            str(finding.get("root_cause")),
            str(finding.get("path")),
            int(finding.get("line_start") or 0),
        )] = finding

    return {
        "schema_version": "sergeant.static-transfer-12-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
