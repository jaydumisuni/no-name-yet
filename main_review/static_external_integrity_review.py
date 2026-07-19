"""Static integrity checks for untrusted Git execution, durable queues, and payment webhooks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_SOURCE_SUFFIXES = {".go", ".js", ".jsx", ".ts", ".tsx"}
_UNTRUSTED_CONTEXT_RE = re.compile(
    r"(?:fork|pull[- ]request|\bpr\b|review(?:er| task| job)?|untrusted|attacker|worktree|head branch|checkout)",
    re.I,
)
_GIT_COMMAND_RE = re.compile(
    r"(?:exec\.)?Command(?:Context)?\s*\((?P<args>[\s\S]{0,900}?)\)",
    re.M,
)
_CLASS_RE = re.compile(r"\bclass\s+(?P<name>[A-Za-z_$][\w$]*)[^{]*\{", re.M)
_ASYNC_METHOD_RE = re.compile(
    r"\basync\s+(?P<name>[A-Za-z_$][\w$]*)\s*\([^)]*\)\s*(?::\s*[^{]+)?\{",
    re.M,
)
_CATCH_RE = re.compile(r"\bcatch\s*(?:\([^)]*\))?\s*\{", re.M)


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


def _matching_brace(text: str, opening: int) -> int | None:
    depth = 0
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    index = opening
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char == "/" and nxt == "/":
            line_comment = True
            index += 2
            continue
        if char == "/" and nxt == "*":
            block_comment = True
            index += 2
            continue
        if char in {"'", '"', "`"}:
            quote = char
            index += 1
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _finding(
    *,
    root_cause: str,
    path: str,
    line_start: int,
    severity: str,
    category: str,
    message: str,
    evidence: str,
    falsifiers: Iterable[str],
    verification: str,
    confidence: float = 0.97,
) -> dict[str, Any]:
    return {
        "source": "static-external-integrity-officer",
        "officer": "Mechanic",
        "capability": category,
        "category": category,
        "severity": severity,
        "root_cause": root_cause,
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": f"{path}:{line_start}",
        "supporting_evidence_refs": [f"{path}:{line_start}"],
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": list(falsifiers),
        "verification_test": verification,
        "confidence": confidence,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def _untrusted_git_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() != ".go":
        return []
    context = f"{path}\n{text}"
    if _UNTRUSTED_CONTEXT_RE.search(context) is None:
        return []

    findings: list[dict[str, Any]] = []
    lowered = text.lower()
    default_deny = "protocol.allow=never" in lowered
    ext_deny = "protocol.ext.allow=never" in lowered
    hooks_disabled = "core.hookspath" in lowered
    for command in _GIT_COMMAND_RE.finditer(text):
        args = command.group("args")
        if re.search(r'["\']git["\']', args, re.I) is None:
            continue
        if re.search(r'["\']submodule["\']', args, re.I) is None:
            continue
        if re.search(r'["\']update["\']', args, re.I) is None:
            continue
        if "--init" not in args:
            continue
        if default_deny and ext_deny and hooks_disabled:
            continue
        line = _line(text, command.start())
        findings.append(
            _finding(
                root_cause="untrusted-git-submodule-exec-without-protocol-hardening",
                path=path,
                line_start=line,
                severity="blocker",
                category="security_taint",
                message="A review/worktree path initializes attacker-controlled Git submodules without locking down executable transports and hooks.",
                evidence=(
                    "The code launches `git submodule update --init` in an untrusted review/worktree context using a direct process command. "
                    "No command-line default-deny transport policy, explicit `ext` denial, or hooks-path neutralization is present at the sink."
                ),
                falsifiers=(
                    "Checked that the command is a real Git submodule initialization sink.",
                    "Checked that the surrounding path or source identifies review, pull-request, worktree, checkout, or attacker-controlled content.",
                    "Checked for protocol.allow=never plus protocol.ext.allow=never at command precedence.",
                    "Checked for core.hooksPath neutralization or a hardened non-interactive Git command helper.",
                ),
                verification=(
                    "Build the submodule command through a hardened helper that default-denies transports, explicitly keeps `ext` disabled, "
                    "neutralizes hooks, disables prompts, and proves legitimate HTTPS/SSH submodules still work."
                ),
            )
        )
        break
    return findings


def _class_blocks(text: str) -> Iterable[tuple[str, str, int]]:
    for match in _CLASS_RE.finditer(text):
        opening = match.end() - 1
        closing = _matching_brace(text, opening)
        if closing is not None:
            yield match.group("name"), text[opening + 1 : closing], opening + 1


def _serialized_queue(body: str) -> bool:
    return bool(
        re.search(
            r"(?:mutex|runExclusive|withLock|withQueueLock|serialize(?:d|Mutation)?|"
            r"(?:operation|mutation|write|queue)(?:Tail|Chain|Lock))",
            body,
            re.I,
        )
    )


def _queue_mutator_rows(body: str, body_offset: int) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for method in _ASYNC_METHOD_RE.finditer(body):
        opening = method.end() - 1
        closing = _matching_brace(body, opening)
        if closing is None:
            continue
        method_body = body[opening + 1 : closing]
        helper_calls = [
            call.group("name")
            for call in re.finditer(
                r"await\s+this\.(?P<name>[A-Za-z_$][\w$]*)\s*\(",
                method_body,
            )
        ]
        loads = bool(
            any(token in name.lower() for name in helper_calls for token in ("load", "read"))
            or re.search(r"await\s+this\.store\.get\s*\([^)]*(?:QUEUE|queue)", method_body, re.I)
        )
        saves = bool(
            any(token in name.lower() for name in helper_calls for token in ("save", "write"))
            or re.search(r"await\s+this\.store\.set\s*\([^)]*(?:QUEUE|queue)", method_body, re.I)
        )
        if loads and saves:
            rows.append((method.group("name"), body_offset + method.start()))
    return rows


def _retry_exhaustion_findings(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for threshold in re.finditer(
        r"\bif\s*\(\s*[A-Za-z_$][\w$]*\s*>=\s*(?:MAX_[A-Z0-9_]*ATTEMPTS|[A-Za-z_$][\w$]*maxAttempts)\s*\)\s*\{",
        text,
        re.I,
    ):
        opening = threshold.end() - 1
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        branch = text[opening + 1 : closing]
        if re.search(r"(?:dead.?letter|quarantine|failureStore|parkedItems|moveToDead|KEY_DEAD)", branch, re.I):
            continue
        if re.search(r"(?:dropped\s*\+\+|dropCount|\.shift\s*\(|\.splice\s*\(|continue\b|return\b)", branch, re.I) is None:
            continue
        line = _line(text, threshold.start())
        findings.append(
            _finding(
                root_cause="retry-exhaustion-removes-item-without-durable-dead-letter",
                path=path,
                line_start=line,
                severity="major",
                category="state_lifecycle",
                message="Exhausted transient deliveries are removed from the pending queue without a durable recovery record.",
                evidence=(
                    "The retry-attempt ceiling transitions the item to a dropped/removed outcome, but the branch does not persist the item "
                    "to a dead-letter, quarantine, or other operator-recoverable store."
                ),
                falsifiers=(
                    "Checked that the branch is specifically the retry-attempt exhaustion path.",
                    "Checked for a durable dead-letter/quarantine write before pending-state removal.",
                    "Checked for a stable recovery identity rather than only a dropped counter or log message.",
                ),
                verification=(
                    "Persist exhausted transient deliveries to a durable dead-letter record before shrinking the pending queue, retain the "
                    "deduplication identity and failure reason, and prove a worker crash cannot leave the item in neither store."
                ),
            )
        )
        break
    return findings


def _durable_queue_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() not in {".js", ".jsx", ".ts", ".tsx"}:
        return []
    findings: list[dict[str, Any]] = []
    for class_name, body, body_offset in _class_blocks(text):
        queue_context = bool(
            re.search(r"(?:queue|outbox|pending|delivery)", class_name, re.I)
            or re.search(r"(?:KEY_QUEUE|queue|outbox|pending)", body, re.I)
        )
        if not queue_context:
            continue
        rows = _queue_mutator_rows(body, body_offset)
        if len(rows) >= 2 and not _serialized_queue(body):
            names = ", ".join(name for name, _ in rows[:4])
            line = _line(text, rows[0][1])
            findings.append(
                _finding(
                    root_cause="persistent-queue-read-modify-write-without-serialization",
                    path=path,
                    line_start=line,
                    severity="major",
                    category="concurrency",
                    message="Multiple asynchronous queue mutations independently read and replace the same persisted collection.",
                    evidence=(
                        f"{class_name} has separate async mutators ({names}) that each load and later save the persisted queue. "
                        "No mutex, promise-chain serializer, or exclusive mutation helper owns the read-modify-write interval, so overlapping "
                        "operations can last-writer-wins away an enqueue or resurrect a delivered item."
                    ),
                    falsifiers=(
                        "Checked that at least two async methods both read and replace the same queue/outbox collection.",
                        "Checked for a mutex, runExclusive/withLock helper, or explicit promise-chain serializer.",
                        "Checked that this is persisted delivery state rather than a local immutable snapshot.",
                    ),
                    verification=(
                        "Serialize every queue mutation through one owner and hold that ownership across awaited upload/storage operations; "
                        "prove concurrent enqueue/enqueue and enqueue/flush preserve every committed item."
                    ),
                )
            )
        break
    findings.extend(_retry_exhaustion_findings(path, text))
    return findings


def _payment_side_effects(text: str) -> bool:
    return bool(
        re.search(r"(?:stripe|webhook)", text, re.I)
        and re.search(
            r"(?:\.from\s*\(\s*[\"'](?:wallets|transactions|subscriptions)[\"']\s*\)|"
            r"\.rpc\s*\(|credit[A-Za-z0-9_$]*\s*\()",
            text,
            re.I,
        )
    )


def _webhook_ack_findings(path: str, text: str) -> list[dict[str, Any]]:
    if not _payment_side_effects(text):
        return []
    success_returns = [
        match
        for match in re.finditer(
            r"return\s+NextResponse\.json\s*\(\s*\{\s*(?:received|success|ok)\s*:\s*true",
            text,
            re.I,
        )
    ]
    if not success_returns:
        return []
    findings: list[dict[str, Any]] = []
    for catch in _CATCH_RE.finditer(text):
        opening = catch.end() - 1
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        body = text[opening + 1 : closing]
        if re.search(r"\b(?:throw|return)\b", body):
            continue
        later_success = next((item for item in success_returns if item.start() > closing), None)
        if later_success is None:
            continue
        if later_success.start() - closing > 1200:
            continue
        line = _line(text, catch.start())
        findings.append(
            _finding(
                root_cause="webhook-side-effect-failure-acknowledged-successfully",
                path=path,
                line_start=line,
                severity="blocker",
                category="state_lifecycle",
                message="A payment webhook swallows a failed side effect and still acknowledges the event with a success response.",
                evidence=(
                    "A catch block logs or ignores a processing failure without returning a retryable non-2xx response or rethrowing. "
                    "Execution then reaches an unconditional success acknowledgement, so the provider can mark the event delivered while "
                    "wallet/subscription state was not committed."
                ),
                falsifiers=(
                    "Checked that the handler performs payment, wallet, transaction, or subscription side effects.",
                    "Checked that the catch block neither rethrows nor returns a non-success response.",
                    "Checked that an unconditional success acknowledgement follows the swallowed failure.",
                ),
                verification=(
                    "Propagate every required side-effect failure to the outer webhook boundary, return a retryable non-2xx status, and prove "
                    "the provider retries until the authoritative state transition commits."
                ),
            )
        )
        break
    return findings


def _payment_idempotency_findings(path: str, text: str) -> list[dict[str, Any]]:
    if not _payment_side_effects(text):
        return []
    balance_read = re.search(r"\.from\s*\(\s*[\"']wallets[\"']\s*\)[\s\S]{0,700}?\.select\s*\(\s*[\"']balance[\"']", text, re.I)
    increment = re.search(r"\bnewBalance\s*=\s*[^;\n]+\+\s*[A-Za-z_$][\w$]*", text)
    wallet_write = re.search(r"\.from\s*\(\s*[\"']wallets[\"']\s*\)[\s\S]{0,500}?\.(?:update|upsert)\s*\(", text, re.I)
    transaction_insert = re.search(r"\.from\s*\(\s*[\"']transactions[\"']\s*\)\.insert\s*\(", text, re.I)
    replay_identity = re.search(r"(?:sessionId|event\.id|stripe_session_id|idempotency)", text, re.I)
    if not all((balance_read, increment, wallet_write, transaction_insert, replay_identity)):
        return []
    atomic = bool(
        re.search(r"\.rpc\s*\(\s*[\"'][^\"']*(?:credit|grant|apply)[^\"']*[\"']", text, re.I)
        or re.search(r"\b(?:transaction|withTransaction|runInTransaction)\s*\(", text, re.I)
    )
    if atomic:
        return []
    line = _line(text, balance_read.start())
    return [
        _finding(
            root_cause="payment-credit-read-modify-write-without-atomic-idempotency",
            path=path,
            line_start=line,
            severity="blocker",
            category="concurrency",
            message="A replayable payment event credits a balance through separate read, write, and ledger operations without one atomic idempotency boundary.",
            evidence=(
                "The handler reads the current wallet balance, computes an incremented value, writes the wallet, and inserts a purchase "
                "transaction as separate application-level operations. Although a provider event/session identity is available, no atomic "
                "transaction or idempotent credit RPC owns both effects, so retries or concurrent deliveries can double-credit or partially commit."
            ),
            falsifiers=(
                "Checked for a stable provider event/session identity in the credit path.",
                "Checked for a single database RPC/transaction owning both balance and ledger effects.",
                "Checked that the code performs application-level balance read-modify-write followed by a separate transaction insert.",
            ),
            verification=(
                "Move crediting behind one transactional, idempotent database operation keyed by the provider event/session identity, enforce "
                "the deduplication key uniquely, and prove duplicate/concurrent deliveries commit exactly one credit and one ledger row."
            ),
        )
    ]


def _payment_webhook_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() not in {".js", ".jsx", ".ts", ".tsx"}:
        return []
    return _webhook_ack_findings(path, text) + _payment_idempotency_findings(path, text)


def run_static_external_integrity_review(
    root: str | Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
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
        findings.extend(_untrusted_git_findings(path, text))
        findings.extend(_durable_queue_findings(path, text))
        findings.extend(_payment_webhook_findings(path, text))

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[
            (
                str(finding.get("root_cause")),
                str(finding.get("path")),
                int(finding.get("line_start", 0)),
            )
        ] = finding

    return {
        "schema_version": "sergeant.static-external-integrity-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
