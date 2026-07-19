"""Static JavaScript/TypeScript remote-to-local state ordering review."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}
_TS_RETURN_RE = r"(?:\s*:\s*[A-Za-z_$][\w$<>,.\[\]\s|&?:]*)?"
_ASYNC_FUNCTION_RE = re.compile(
    rf"(?:async\s+function\s+(?P<decl>[A-Za-z_$][\w$]*)\s*\([^)]*\){_TS_RETURN_RE}|"
    rf"(?:const|let|var)\s+(?P<arrow>[A-Za-z_$][\w$]*)\s*=\s*async\s*\([^)]*\){_TS_RETURN_RE}\s*=>)\s*\{{",
    re.M,
)
_PLAIN_FUNCTION_RE = re.compile(
    rf"function\s+(?P<name>[A-Za-z_$][\w$]*)\s*\([^)]*\){_TS_RETURN_RE}\s*\{{",
    re.M,
)
_MODULE_EMPTY_RE = re.compile(
    r"^(?:export\s+)?(?:let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:null|undefined|false)\s*;?",
    re.M,
)
_AWAIT_STATEMENT_RE = re.compile(r"\bawait\s+(?P<statement>[\s\S]{1,900}?);", re.M)
_AWAIT_ASSIGNMENT_RE = re.compile(
    r"(?:const|let|var)\s+(?P<value>[A-Za-z_$][\w$]*)\s*=\s*"
    r"await\s+(?P<call>[\s\S]{1,1000}?);",
    re.M,
)
_EFFECT_RE = re.compile(r"\buseEffect\s*\(\s*\(\s*\)\s*=>\s*\{", re.M)
_AUTH_MUTATION_NAME_RE = re.compile(
    r"^(?:login|logout|signIn|signOut|authenticate|revokeSession|loginWithPasskey)$",
    re.I,
)
_PRINCIPAL_FETCH_RE = re.compile(
    r"\b(?:fetchMe|me|getMe|loadMe|fetchCurrentUser|getCurrentUser|"
    r"fetchPrincipal|getPrincipal|fetchSession|getSession)\s*\(",
    re.I,
)
_PRINCIPAL_SETTER_RE = re.compile(
    r"\bset(?:Me|User|CurrentUser|Principal|Session|AuthenticatedUser)\s*\(",
    re.I,
)
_AUTH_SIGNAL_LISTENER_RE = re.compile(
    r"(?:addEventListener\s*\(|onAuthStateChanged\s*\(|BroadcastChannel\s*\(|"
    r"\.subscribe\s*\(|invalidateQueries\s*\()",
    re.I,
)
_AUTH_SIGNAL_DISPATCH_RE = re.compile(
    r"(?:dispatchEvent\s*\(|\.postMessage\s*\(|invalidateQueries\s*\(|"
    r"notifyAuth|emitAuth|publishAuth)",
    re.I,
)


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


def _functions(text: str, pattern: re.Pattern[str]) -> dict[str, tuple[str, int]]:
    functions: dict[str, tuple[str, int]] = {}
    for match in pattern.finditer(text):
        groups = match.groupdict()
        name = groups.get("decl") or groups.get("arrow") or groups.get("name")
        if not name:
            continue
        opening = match.end() - 1
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        functions[name] = (text[opening + 1 : closing], opening + 1)
    return functions


def _base_finding(
    *,
    root_cause: str,
    path: str,
    line_start: int,
    message: str,
    evidence: str,
    supporting: Iterable[str],
    falsifiers: Iterable[str],
    verification: str,
    confidence: float,
) -> dict[str, Any]:
    return {
        "source": "static-js-remote-state-officer",
        "officer": "Mechanic",
        "capability": "state_lifecycle",
        "category": "state_lifecycle",
        "severity": "major",
        "root_cause": root_cause,
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": f"{path}:{line_start}",
        "supporting_evidence_refs": list(supporting),
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": list(falsifiers),
        "verification_test": verification,
        "confidence": confidence,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def _remote_local_finding(
    *,
    path: str,
    function_name: str,
    shared: str,
    await_line: int,
    helper_name: str,
    helper_line: int,
    declaration_line: int,
) -> dict[str, Any]:
    return _base_finding(
        root_cause="local-state-not-established-before-await",
        path=path,
        line_start=await_line,
        message="An async action awaits remote persistence before establishing local state required by its immediate continuation.",
        evidence=(
            f"{function_name} writes the remote {shared} resource and suspends at line {await_line} while local {shared} "
            f"still has its empty initial value; {helper_name} then dereferences that local state at line {helper_line}."
        ),
        supporting=(
            f"{path}:{declaration_line}",
            f"{path}:{await_line}",
            f"{path}:{helper_line}",
        ),
        falsifiers=(
            "Checked for assignment of the consumed local/shared state before the await.",
            "Checked that the awaited remote statement names the same resource identity as the local state.",
            "Checked that the immediate continuation calls a helper that dereferences the local state.",
            "Checked that the local state is module-scoped and starts empty rather than being call-local.",
        ),
        verification=(
            "Establish local ownership/state before the remote await, roll it back on persistence failure if needed, "
            "and prove the immediate continuation always receives the new identity."
        ),
        confidence=0.97,
    )


def _remote_local_ordering(path: str, text: str) -> list[dict[str, Any]]:
    async_functions = _functions(text, _ASYNC_FUNCTION_RE)
    helpers = _functions(text, _PLAIN_FUNCTION_RE)
    declarations = {
        match.group("name"): (match.start(), _line(text, match.start()))
        for match in _MODULE_EMPTY_RE.finditer(text)
    }
    findings: list[dict[str, Any]] = []

    for function_name, (body, body_offset) in async_functions.items():
        for awaited in _AWAIT_STATEMENT_RE.finditer(body):
            before = body[: awaited.start()]
            after = body[awaited.end() :]
            remote_statement = awaited.group("statement")
            await_line = _line(text, body_offset + awaited.start())
            for helper_name, (helper_body, _) in helpers.items():
                helper_call = re.search(rf"\b{re.escape(helper_name)}\s*\(", after)
                if helper_call is None:
                    continue
                helper_line = _line(text, body_offset + awaited.end() + helper_call.start())
                for shared, (_, declaration_line) in declarations.items():
                    if not re.search(rf"\b{re.escape(shared)}\s*(?:\?\.|\.|\[)", helper_body):
                        continue
                    if re.search(rf"\b{re.escape(shared)}\s*=", before):
                        continue
                    if shared.lower() not in remote_statement.lower():
                        continue
                    findings.append(
                        _remote_local_finding(
                            path=path,
                            function_name=function_name,
                            shared=shared,
                            await_line=await_line,
                            helper_name=helper_name,
                            helper_line=helper_line,
                            declaration_line=declaration_line,
                        )
                    )
    return findings


def _request_guarded(before: str, after_before_publish: str) -> bool:
    token = re.search(
        r"(?:const|let)\s+(?P<local>[A-Za-z_$][\w$]*)\s*=\s*"
        r"\+\+\s*(?P<owner>[A-Za-z_$][\w$]*(?:\.current)?)",
        before,
    )
    if token is None:
        return False
    local = token.group("local")
    owner = token.group("owner")
    return bool(
        re.search(
            rf"if\s*\([^)]*(?:{re.escape(local)}\s*!==?\s*{re.escape(owner)}|"
            rf"{re.escape(owner)}\s*!==?\s*{re.escape(local)})[^)]*\)\s*(?:\{{\s*)?return\b",
            after_before_publish,
        )
    )


def _imperative_stale_publication(path: str, text: str) -> list[dict[str, Any]]:
    if "useEffect" not in text:
        return []
    findings: list[dict[str, Any]] = []
    functions = _functions(text, _ASYNC_FUNCTION_RE)
    publication_methods = (
        "setData",
        "setPaintProperty",
        "setLayoutProperty",
        "setGeoJSON",
        "replaceData",
        "updateSource",
    )
    method_pattern = "|".join(publication_methods)

    for function_name, (body, body_offset) in functions.items():
        call_count = len(re.findall(rf"\b{re.escape(function_name)}\s*\(", text))
        reference_count = len(
            re.findall(
                rf"(?:setTimeout|queueMicrotask|requestAnimationFrame)\s*\(\s*{re.escape(function_name)}\b",
                text,
            )
        )
        if call_count + reference_count < 3:
            continue
        for awaited in _AWAIT_ASSIGNMENT_RE.finditer(body):
            value = awaited.group("value")
            after = body[awaited.end() :]
            publication = re.search(
                rf"\.\s*(?P<method>{method_pattern})\s*\([^;]{{0,500}}\b{re.escape(value)}\b",
                after,
                re.S,
            )
            if publication is None:
                continue
            before = body[: awaited.start()]
            between = after[: publication.start()]
            if _request_guarded(before, between):
                continue
            await_line = _line(text, body_offset + awaited.start())
            publish_line = _line(text, body_offset + awaited.end() + publication.start())
            findings.append(
                _base_finding(
                    root_cause="superseded-request-publishes-imperative-state",
                    path=path,
                    line_start=await_line,
                    message="A re-entrant async refresh can publish an older response into an imperative UI resource after a newer refresh has started.",
                    evidence=(
                        f"{function_name} has multiple invocation paths, awaits a response into {value} at line {await_line}, "
                        f"and publishes it through {publication.group('method')} at line {publish_line}. No request-generation "
                        "identity rejects a superseded response before the imperative mutation."
                    ),
                    supporting=(f"{path}:{await_line}", f"{path}:{publish_line}"),
                    falsifiers=(
                        "Checked that the async refresh has multiple call or scheduled-reference paths.",
                        "Checked that fetched response data is published through an imperative source/map mutation after the await.",
                        "Checked for a monotonically increasing request/generation token captured before the await.",
                        "Checked for a post-await token comparison that rejects an older invocation before publication.",
                    ),
                    verification=(
                        "Give each refresh a monotonic request identity and reject any response that is no longer current before "
                        "calling setData or another imperative publisher; optionally debounce dependency-driven refreshes."
                    ),
                    confidence=0.96,
                )
            )
            break
    return findings


def _effect_blocks(text: str) -> list[tuple[str, str, int]]:
    rows: list[tuple[str, str, int]] = []
    for effect in _EFFECT_RE.finditer(text):
        opening = effect.end() - 1
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        body = text[opening + 1 : closing]
        tail = text[closing + 1 : closing + 320]
        deps = re.search(r",\s*\[(?P<deps>[^\]]*)\]\s*\)", tail, re.S)
        if deps is None:
            continue
        rows.append((body, deps.group("deps"), opening + 1))
    return rows


def _latest_request_guard(text: str) -> bool:
    counter = re.search(
        r"(?:let|const)\s+(?P<counter>[A-Za-z_$][\w$]*(?:Request|RequestId|Epoch|Generation)[A-Za-z0-9_$]*)\s*=\s*0",
        text,
        re.I,
    )
    if counter is None:
        return False
    owner = counter.group("counter")
    captured = re.search(
        rf"(?:const|let)\s+(?P<local>[A-Za-z_$][\w$]*)\s*=\s*\+\+\s*{re.escape(owner)}",
        text,
    )
    if captured is None:
        return False
    local = captured.group("local")
    return bool(
        re.search(
            rf"(?:{re.escape(local)}\s*===?\s*{re.escape(owner)}|"
            rf"{re.escape(owner)}\s*===?\s*{re.escape(local)})",
            text,
        )
    )


def _auth_mutation_refs(texts: dict[str, str]) -> list[tuple[str, int]]:
    refs: list[tuple[str, int]] = []
    for path, text in texts.items():
        for name, (body, body_offset) in _functions(text, _ASYNC_FUNCTION_RE).items():
            if _AUTH_MUTATION_NAME_RE.match(name) is None:
                continue
            if "fetch(" not in body or not re.search(r"auth|session|login|logout", body, re.I):
                continue
            refs.append((path, _line(text, body_offset)))
    return refs


def _auth_principal_cache_drift(texts: dict[str, str]) -> list[dict[str, Any]]:
    mutations = _auth_mutation_refs(texts)
    if not mutations:
        return []
    dispatch_present = any(_AUTH_SIGNAL_DISPATCH_RE.search(text) for text in texts.values())
    findings: list[dict[str, Any]] = []

    for path, text in texts.items():
        for effect_body, dependencies, effect_offset in _effect_blocks(text):
            if dependencies.strip():
                continue
            if _PRINCIPAL_FETCH_RE.search(effect_body) is None:
                continue
            if _PRINCIPAL_SETTER_RE.search(effect_body) is None:
                continue
            listener_present = bool(_AUTH_SIGNAL_LISTENER_RE.search(effect_body))
            token_present = _latest_request_guard(effect_body)
            if listener_present and dispatch_present and token_present:
                continue
            effect_line = _line(text, effect_offset)
            mutation_path, mutation_line = mutations[0]
            missing: list[str] = []
            if not listener_present:
                missing.append("principal-cache invalidation listener")
            if not dispatch_present:
                missing.append("successful auth-mutation notification")
            if listener_present and dispatch_present and not token_present:
                missing.append("latest-request ownership guard")
            findings.append(
                _base_finding(
                    root_cause="auth-session-change-not-invalidating-client-principal",
                    path=path,
                    line_start=effect_line,
                    message="An always-mounted client principal cache is not safely synchronized with successful authentication changes.",
                    evidence=(
                        f"The mount-only principal effect at line {effect_line} fetches and stores the current principal, while "
                        f"an auth mutation exists at {mutation_path}:{mutation_line}. Missing contract: {', '.join(missing)}. "
                        "A same-route login/logout can therefore leave the cached principal stale, and overlapping refetches need "
                        "latest-request ownership before publishing."
                    ),
                    supporting=(f"{path}:{effect_line}", f"{mutation_path}:{mutation_line}"),
                    falsifiers=(
                        "Checked that the principal cache is initialized by a mount-only effect and writes client state.",
                        "Checked that changed files contain successful login/logout/session mutation functions.",
                        "Checked for a shared event, subscription, query invalidation, or auth-state channel from mutation to cache.",
                        "When refetch synchronization exists, checked for a monotonic request identity guarding overlapping responses.",
                    ),
                    verification=(
                        "Emit a browser-safe auth-changed signal only after successful session mutations, subscribe the persistent "
                        "principal cache to refetch, remove the listener on cleanup, and gate every response with a monotonic latest-request token."
                    ),
                    confidence=0.96,
                )
            )
    return findings


def run_static_js_remote_state_review(
    root: str | Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    findings: list[dict[str, Any]] = []
    readable: list[str] = []
    texts: dict[str, str] = {}

    for path in changed:
        if Path(path).suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        texts[path] = text
        findings.extend(_remote_local_ordering(path, text))
        findings.extend(_imperative_stale_publication(path, text))

    findings.extend(_auth_principal_cache_drift(texts))

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
        "schema_version": "sergeant.static-js-remote-state-review.v2",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
