"""Static publication-lifetime checks for async provider and UI flows."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_SOURCE_SUFFIXES = {".dart", ".js", ".jsx", ".ts", ".tsx"}
_JS_ASYNC_RE = re.compile(
    r"(?:async\s+function\s+(?P<decl>[A-Za-z_$][\w$]*)\s*\([^)]*\)|"
    r"(?:const|let|var)\s+(?P<arrow>[A-Za-z_$][\w$]*)\s*=\s*async\s*\([^)]*\)\s*=>)\s*\{",
    re.M,
)
_EFFECT_RE = re.compile(r"\buseEffect\s*\(\s*\(\s*\)\s*=>\s*\{", re.M)


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


def _js_functions(text: str) -> dict[str, tuple[str, int]]:
    functions: dict[str, tuple[str, int]] = {}
    for match in _JS_ASYNC_RE.finditer(text):
        groups = match.groupdict()
        name = groups.get("decl") or groups.get("arrow")
        if not name:
            continue
        opening = match.end() - 1
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        functions[name] = (text[opening + 1 : closing], opening + 1)
    return functions


def _finding(
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
        "source": "static-async-publication-officer",
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


def _dart_provider_ref_after_await(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if "@riverpod" not in text:
        return findings
    build_re = re.compile(r"Future(?:<[^>{}]*>)?\s+build\s*\([^)]*\)\s*async\s*\{", re.M)
    for build in build_re.finditer(text):
        opening = build.end() - 1
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        body = text[opening + 1 : closing]
        await_match = re.search(r"\bawait\b", body)
        if await_match is None:
            continue
        after = body[await_match.end() :]
        ref_use = re.search(r"\bref\s*\.\s*(?:read|watch|invalidate|invalidateSelf|keepAlive)\s*\(", after)
        if ref_use is None:
            continue
        between = after[: ref_use.start()]
        mounted_guard = re.search(
            r"if\s*\(\s*!?\s*ref\.mounted\s*\)\s*(?:return|\{|ref\.)",
            between,
        )
        if mounted_guard is not None:
            continue
        await_line = _line(text, opening + 1 + await_match.start())
        ref_line = _line(text, opening + 1 + await_match.end() + ref_use.start())
        findings.append(
            _finding(
                root_cause="disposed-provider-ref-after-await",
                path=path,
                line_start=await_line,
                message="An auto-dispose provider touches its lifecycle-bound ref after an async gap without proving the provider is still mounted.",
                evidence=(
                    f"The Riverpod build method suspends at line {await_line} and accesses ref again at line {ref_line}. "
                    "An auto-disposed provider can be torn down while suspended, making the resumed ref access invalid."
                ),
                supporting=(f"{path}:{await_line}", f"{path}:{ref_line}"),
                falsifiers=(
                    "Checked that the method belongs to an @riverpod provider build.",
                    "Checked that lifecycle-bound ref access occurs after the first await.",
                    "Checked for a ref.mounted guard before the resumed ref access.",
                ),
                verification="Capture required ref-backed dependencies before awaiting, or guard post-await lifecycle operations with ref.mounted, then prove provider disposal during the fetch cannot crash.",
                confidence=0.98,
            )
        )
    return findings


def _superseded_request_publication(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    functions = _js_functions(text)
    for name, (body, body_offset) in functions.items():
        if len(re.findall(rf"\b{re.escape(name)}\s*\(", text)) < 2:
            continue
        awaits = list(re.finditer(r"\bawait\b", body))
        if not awaits:
            continue
        first_await = awaits[0]
        before = body[: first_await.start()]
        after = body[first_await.end() :]
        if re.search(r"\bset[A-Z][A-Za-z0-9_]*\s*\(", before) is None:
            continue
        state_write = re.search(r"\bset[A-Z][A-Za-z0-9_]*\s*\(", after)
        if state_write is None:
            continue
        request_identity = re.search(
            r"(?:request|load|generation|epoch)[A-Za-z0-9_]*(?:Ref)?\.current|\+\+\s*[A-Za-z_$][\w$]*\.current",
            body,
            re.I,
        )
        post_guard = re.search(
            r"if\s*\([^)]*(?:request|load|generation|epoch)[^)]*(?:!==|!=)[^)]*\)\s*return",
            after[: state_write.start()],
            re.I,
        )
        if request_identity is not None and post_guard is not None:
            continue
        await_line = _line(text, body_offset + first_await.start())
        write_line = _line(text, body_offset + first_await.end() + state_write.start())
        findings.append(
            _finding(
                root_cause="superseded-request-publishes-component-state",
                path=path,
                line_start=await_line,
                message="A re-entrant async loader can publish state from an older invocation after a newer invocation has started.",
                evidence=(
                    f"{name} has multiple call sites, sets loading state before suspending at line {await_line}, and publishes component state at line {write_line}. "
                    "No per-invocation request/generation identity gates the post-await write."
                ),
                supporting=(f"{path}:{await_line}", f"{path}:{write_line}"),
                falsifiers=(
                    "Checked that the async function has more than one call site.",
                    "Checked for a request-id, generation, or epoch token captured per invocation.",
                    "Checked for a post-await comparison that rejects a superseded invocation.",
                ),
                verification="Assign each invocation a monotonically increasing request identity and gate every post-await state publication on still being the latest request.",
                confidence=0.95,
            )
        )
    return findings


def _effect_calls(text: str) -> list[tuple[set[str], set[str], int]]:
    rows: list[tuple[set[str], set[str], int]] = []
    for effect in _EFFECT_RE.finditer(text):
        opening = effect.end() - 1
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        body = text[opening + 1 : closing]
        tail = text[closing + 1 : closing + 250]
        dependencies = re.search(r",\s*\[(?P<deps>[^\]]*)\]\s*\)", tail)
        if dependencies is None:
            continue
        deps = set(re.findall(r"[A-Za-z_$][\w$]*", dependencies.group("deps")))
        calls = set(re.findall(r"\b([A-Za-z_$][\w$]*)\s*\(", body))
        rows.append((deps, calls, opening + 1))
    return rows


def _stale_session_closure(path: str, text: str) -> list[dict[str, Any]]:
    auth_match = re.search(
        r"\{(?P<names>[^}]*\b(?:loggedIn|user|session|authenticated)\b[^}]*)\}\s*=\s*useAppSelector\(",
        text,
        re.I,
    )
    if auth_match is None:
        return []
    auth_names = set(re.findall(r"\b(?:loggedIn|user|session|authenticated)\b", auth_match.group("names"), re.I))
    functions = _js_functions(text)
    live_ref = re.search(
        r"(?:loggedIn|user|session|authenticated)[A-Za-z0-9_]*Ref\s*=\s*useRef\(",
        text,
        re.I,
    )
    findings: list[dict[str, Any]] = []
    for deps, calls, _ in _effect_calls(text):
        if not any(dep.lower() in {name.lower() for name in auth_names} for dep in deps):
            continue
        for name in calls:
            row = functions.get(name)
            if row is None:
                continue
            body, body_offset = row
            await_match = re.search(r"\bawait\b", body)
            if await_match is None:
                continue
            dispatch = re.search(r"\bdispatch\s*\(", body[await_match.end() :])
            if dispatch is None:
                continue
            between = body[await_match.end() : await_match.end() + dispatch.start()]
            live_guard = re.search(
                r"if\s*\([^)]*(?:loggedIn|user|session|authenticated)[A-Za-z0-9_]*Ref\.current[^)]*\)\s*(?:\{|return)",
                between,
                re.I,
            )
            if live_ref is not None and live_guard is not None:
                continue
            await_line = _line(text, body_offset + await_match.start())
            dispatch_line = _line(text, body_offset + await_match.end() + dispatch.start())
            findings.append(
                _finding(
                    root_cause="stale-session-closure-publishes-after-await",
                    path=path,
                    line_start=await_line,
                    message="An async callback started from a session-dependent effect can dispatch after that session lifetime has ended.",
                    evidence=(
                        f"The effect depends on session identity and calls {name}; {name} suspends at line {await_line} and dispatches at line {dispatch_line}. "
                        "No live session ref is rechecked after the await, so a stale closure can republish state after teardown."
                    ),
                    supporting=(f"{path}:{await_line}", f"{path}:{dispatch_line}"),
                    falsifiers=(
                        "Checked that a session/user-dependent effect invokes the async callback.",
                        "Checked that the callback dispatches after awaiting external work.",
                        "Checked for a live session/auth ref and post-await guard before dispatch.",
                    ),
                    verification="Mirror session validity into a live ref or cancellation token and recheck it after every await before dispatching persistent state.",
                    confidence=0.96,
                )
            )
            return findings
    return findings


def run_static_async_publication_review(
    root: str | Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    findings: list[dict[str, Any]] = []
    readable: list[str] = []
    for path in changed:
        suffix = Path(path).suffix.lower()
        if suffix not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        if suffix == ".dart":
            findings.extend(_dart_provider_ref_after_await(path, text))
        else:
            findings.extend(_superseded_request_publication(path, text))
            findings.extend(_stale_session_closure(path, text))
    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding["root_cause"]), str(finding["path"]), int(finding["line_start"]))] = finding
    return {
        "schema_version": "sergeant.static-async-publication-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
