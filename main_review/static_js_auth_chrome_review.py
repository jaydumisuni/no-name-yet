"""Static cross-file auth synchronization checks for long-lived SPA chrome.

The rule models a browser session producer and a topbar/header/menu consumer.
It reports only when authoritative user state is mutated, an auth-sensitive
chrome surface is mounted for the SPA lifetime, and no matching invalidation
channel connects the two.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from .static_js_auth_transition_review import run_static_js_auth_transition_review

_SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}
_MOUNT_CHROME_RE = re.compile(
    r"(?:export\s+)?function\s+(?P<name>mount(?:Topbar|Header|Nav|Menu|Chrome)[A-Za-z0-9_$]*)"
    r"\s*\([^)]*\)\s*\{",
    re.I | re.M,
)
_AUTH_SURFACE_RE = re.compile(
    r"(?:open-auth|sign[- ]?in|sign[- ]?out|log[- ]?in|log[- ]?out|profile|avatar|account)",
    re.I,
)
_SESSION_MUTATION_RE = re.compile(
    r"(?P<method>set(?:User|Session|Principal)|clearSession|signOut|logout)\s*\([^)]*\)\s*\{"
    r"(?P<body>[\s\S]{0,900}?)\}",
    re.I | re.M,
)
_STATE_ASSIGN_RE = re.compile(
    r"\b(?P<state>[_$A-Za-z][\w$]*(?:User|Session|Principal))\s*=",
    re.I,
)
_EVENT_DISPATCH_RE = re.compile(
    r"dispatchEvent\s*\(\s*new\s+(?:CustomEvent|Event)\s*\(\s*[\"']"
    r"(?P<event>[^\"']*(?:auth|session|user)[^\"']*)[\"']",
    re.I | re.M,
)
_EVENT_LISTENER_RE = re.compile(
    r"addEventListener\s*\(\s*[\"'](?P<event>[^\"']*(?:auth|session|user)[^\"']*)[\"']",
    re.I | re.M,
)
_NATIVE_AUTH_LISTENER_RE = re.compile(
    r"(?:onAuthStateChanged\s*\(|(?:auth|session|principal)[A-Za-z0-9_$]*\.subscribe\s*\(|"
    r"BroadcastChannel\s*\(\s*[\"'][^\"']*(?:auth|session|user))",
    re.I,
)
_AUTH_PROBE_RE = re.compile(
    r"(?:/api/(?:auth/)?(?:me|session|user)|fetchAuthUser\s*\(|fetchCurrentUser\s*\(|"
    r"getCurrentUser\s*\(|SpyglassSession\.user\b)",
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


def _chrome_mounts(texts: dict[str, str]) -> list[tuple[str, str, int]]:
    mounts: list[tuple[str, str, int]] = []
    for path, text in texts.items():
        if _AUTH_SURFACE_RE.search(text) is None:
            continue
        for match in _MOUNT_CHROME_RE.finditer(text):
            opening = match.end() - 1
            closing = _matching_brace(text, opening)
            if closing is None:
                continue
            body = text[opening + 1 : closing]
            if not re.search(r"(?:innerHTML\s*=|replaceChild\s*\(|addEventListener\s*\()", body):
                continue
            mounts.append((path, match.group("name"), _line(text, match.start())))
    return mounts


def _session_mutations(texts: dict[str, str]) -> list[tuple[str, str, str, int]]:
    mutations: list[tuple[str, str, str, int]] = []
    for path, text in texts.items():
        for match in _SESSION_MUTATION_RE.finditer(text):
            assignment = _STATE_ASSIGN_RE.search(match.group("body"))
            if assignment is None:
                continue
            mutations.append(
                (
                    path,
                    match.group("method"),
                    assignment.group("state"),
                    _line(text, match.start()),
                )
            )
    return mutations


def _event_names(pattern: re.Pattern[str], text: str) -> set[str]:
    return {match.group("event").lower() for match in pattern.finditer(text)}


def _synchronized(producer_text: str, consumer_text: str) -> bool:
    dispatched = _event_names(_EVENT_DISPATCH_RE, producer_text)
    listened = _event_names(_EVENT_LISTENER_RE, consumer_text)
    if dispatched & listened:
        return True
    if _NATIVE_AUTH_LISTENER_RE.search(consumer_text):
        return True
    return False


def _finding(
    *,
    consumer_path: str,
    mount_name: str,
    mount_line: int,
    producer_path: str,
    mutation_name: str,
    state_name: str,
    mutation_line: int,
    consumer_has_probe: bool,
) -> dict[str, Any]:
    missing = "matching auth-state listener and producer notification"
    if consumer_has_probe:
        missing = "post-mutation invalidation listener; the existing auth probe only runs during mount/navigation"
    return {
        "source": "static-js-remote-state-officer",
        "officer": "Mechanic",
        "capability": "state_lifecycle",
        "category": "state_lifecycle",
        "severity": "major",
        "root_cause": "auth-session-change-not-invalidating-mounted-chrome",
        "path": consumer_path,
        "line_start": mount_line,
        "line_end": mount_line,
        "evidence_ref": f"{consumer_path}:{mount_line}",
        "supporting_evidence_refs": [
            f"{consumer_path}:{mount_line}",
            f"{producer_path}:{mutation_line}",
        ],
        "message": "A long-lived SPA chrome surface is not invalidated when authoritative browser-session identity changes.",
        "evidence": (
            f"{mount_name} mounts an auth-sensitive chrome surface at {consumer_path}:{mount_line}. "
            f"{mutation_name} mutates authoritative {state_name} at {producer_path}:{mutation_line}, but the changed files "
            f"provide no {missing}. A same-route sign-in or sign-out can therefore leave the mounted chrome stale until reload."
        ),
        "falsifiers_checked": [
            "Checked that the consumer is a mounted topbar/header/nav/menu/chrome function that renders an authentication surface.",
            "Checked that a changed source file mutates authoritative user/session/principal state through a session lifecycle method.",
            "Checked for an exact matching auth/session/user event dispatched by the producer and listened to by the mounted consumer.",
            "Checked for native auth-state subscriptions or broadcast channels in the consumer.",
            "Distinguished a one-time auth probe from a post-mutation invalidation channel.",
        ],
        "verification_test": (
            "After every successful session mutation, publish a browser-safe auth-state signal carrying or invalidating the principal; "
            "subscribe the long-lived chrome on mount, update only its auth region, and remove the listener on unmount. Prove login and "
            "logout update the mounted chrome without navigation or reload."
        ),
        "confidence": 0.97,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def run_static_js_auth_chrome_review(
    root: str | Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    texts: dict[str, str] = {}
    readable: list[str] = []
    for path in changed:
        if Path(path).suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        texts[path] = text
        readable.append(path)

    mounts = _chrome_mounts(texts)
    mutations = _session_mutations(texts)
    findings: list[dict[str, Any]] = []
    for consumer_path, mount_name, mount_line in mounts:
        consumer_text = texts[consumer_path]
        for producer_path, mutation_name, state_name, mutation_line in mutations:
            producer_text = texts[producer_path]
            if _synchronized(producer_text, consumer_text):
                continue
            findings.append(
                _finding(
                    consumer_path=consumer_path,
                    mount_name=mount_name,
                    mount_line=mount_line,
                    producer_path=producer_path,
                    mutation_name=mutation_name,
                    state_name=state_name,
                    mutation_line=mutation_line,
                    consumer_has_probe=bool(_AUTH_PROBE_RE.search(consumer_text)),
                )
            )
            break

    transition = run_static_js_auth_transition_review(root_path, changed)
    findings.extend(
        dict(item)
        for item in transition.get("findings", [])
        if isinstance(item, dict)
    )

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
        "schema_version": "sergeant.static-js-auth-chrome-review.v2",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "static_js_auth_transition_review": transition,
        "executed_project_code": False,
    }
