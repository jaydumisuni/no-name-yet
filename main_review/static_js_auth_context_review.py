"""Static cross-file authentication context propagation checks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from .static_credential_destination_review import run_static_credential_destination_review

_SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}
_NEXT_ROUTER_IMPORT_RE = re.compile(
    r"import\s*\{[^}]*\buseRouter\b[^}]*\}\s*from\s*[\"'](?P<module>[^\"']*navigation[^\"']*)[\"']",
    re.I | re.M,
)
_AUTH_CONTEXT_RE = re.compile(
    r"\{(?P<fields>[^}]*\b(?:signIn|signInWithGoogle|login|authenticate)\b[^}]*)\}\s*=\s*useAuth\s*\(",
    re.I | re.M,
)
_AWAIT_CONTEXT_AUTH_RE = re.compile(
    r"await\s+(?P<method>signInWithGoogle|signIn|login|authenticate)\s*\(",
    re.I,
)
_ROUTER_NAV_RE = re.compile(r"\brouter\.(?P<method>push|replace)\s*\(", re.I)
_AUTH_HANDOFF_RE = re.compile(
    r"(?:startTransition\s*\(|navigateAfterAuth\s*\(|router\.refresh\s*\(|"
    r"invalidateQueries\s*\(|refetchQueries\s*\()",
    re.I,
)
_SESSION_QUERY_RE = re.compile(
    r"(?:SESSION_QUERY_KEY\s*=\s*\[\s*[\"']session[\"']\s*\]|"
    r"queryKey\s*:\s*\[\s*[\"']session[\"']\s*\])",
    re.I,
)
_STICKY_QUERY_RE = re.compile(
    r"(?:staleTime\s*:|refetchOnMount\s*:\s*false|retryOnMount\s*:\s*false|sessionQueryOptions)",
    re.I,
)
_QUERY_SYNC_RE = re.compile(
    r"queryClient\.(?:invalidateQueries|refetchQueries|resetQueries|clear)\s*\(",
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
        "source": "static-js-auth-context-officer",
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


def _next_auth_context_handoffs(path: str, text: str) -> list[dict[str, Any]]:
    router_import = _NEXT_ROUTER_IMPORT_RE.search(text)
    if router_import is None or _AUTH_CONTEXT_RE.search(text) is None:
        return []
    findings: list[dict[str, Any]] = []
    for auth_call in _AWAIT_CONTEXT_AUTH_RE.finditer(text):
        navigation = _ROUTER_NAV_RE.search(text, auth_call.end(), auth_call.end() + 900)
        if navigation is None:
            continue
        between = text[auth_call.end() : navigation.start()]
        if _AUTH_HANDOFF_RE.search(between):
            continue
        auth_line = _line(text, auth_call.start())
        nav_line = _line(text, navigation.start())
        findings.append(
            _finding(
                root_cause="post-auth-navigation-before-router-cache-handoff",
                path=path,
                line_start=nav_line,
                message="A context-supplied authentication success navigates directly into a Next.js Router Cache built under the prior session.",
                evidence=(
                    f"The component obtains {auth_call.group('method')} from useAuth, awaits it at line {auth_line}, then calls "
                    f"router.{navigation.group('method')} at line {nav_line}. No transition/refresh/invalidation handoff separates the "
                    f"new cookie state from the cached navigation result supplied by {router_import.group('module')}."
                ),
                supporting=(f"{path}:{auth_line}", f"{path}:{nav_line}"),
                falsifiers=(
                    "Checked that the auth method is supplied by useAuth rather than an unrelated local helper.",
                    "Checked that the file uses a Next-style navigation adapter exposing useRouter.",
                    "Checked that router.push/replace follows the awaited authentication call.",
                    "Checked for startTransition, a dedicated navigateAfterAuth helper, router.refresh, or explicit cache invalidation before navigation.",
                ),
                verification=(
                    "Route successful authentication through one post-auth navigation helper that schedules the Router Cache handoff "
                    "after the new cookie is observable, and prove cached middleware redirects cannot bounce the user back to sign-in."
                ),
                confidence=0.96,
            )
        )
    return findings


def _user_context_provider(texts: dict[str, str]) -> tuple[str, int] | None:
    for path, text in texts.items():
        refresh = re.search(
            r"async\s+function\s+refreshUser\s*\([^)]*\)\s*\{(?P<body>[\s\S]{0,1400}?)\}",
            text,
            re.I,
        )
        if refresh is None:
            continue
        body = refresh.group("body")
        if re.search(r"await\s+(?:getCurrentUser|fetchCurrentUser|loadCurrentUser)\s*\(", body, re.I) is None:
            continue
        if re.search(r"\bsetUser\s*\(", body) is None:
            continue
        if re.search(r"Provider\s+value\s*=\s*\{\{[^}]*\brefreshUser\b", text, re.I | re.S) is None:
            continue
        return path, _line(text, refresh.start())
    return None


def _user_context_chrome(texts: dict[str, str]) -> tuple[str, int] | None:
    for path, text in texts.items():
        component = re.search(
            r"(?:function|const)\s+(?:Navbar|Topbar|Header|Sidebar|Chrome)\b",
            text,
            re.I,
        )
        if component is None:
            continue
        if re.search(r"\{[^}]*\buser\b[^}]*\}\s*=\s*useUser\s*\(", text, re.I) is None:
            continue
        return path, _line(text, component.start())
    return None


def _token_navigation_without_context_refresh(
    path: str,
    text: str,
    provider: tuple[str, int],
    chrome: tuple[str, int],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    login = re.search(r"await\s+(?:login|signIn|authenticate)\s*\(", text, re.I)
    if login is None:
        return findings
    token_write = re.search(
        r"localStorage\.setItem\s*\(\s*[\"'](?:token|access_token|auth_token|session)[\"']",
        text[login.end() : login.end() + 1200],
        re.I,
    )
    if token_write is None:
        return findings
    write_offset = login.end() + token_write.start()
    navigation = re.search(r"\bnavigate\s*\(", text[write_offset : write_offset + 1000], re.I)
    if navigation is None:
        return findings
    nav_offset = write_offset + navigation.start()
    between = text[write_offset:nav_offset]
    if re.search(r"await\s+refreshUser\s*\(", between, re.I):
        return findings
    login_line = _line(text, login.start())
    write_line = _line(text, write_offset)
    nav_line = _line(text, nav_offset)
    provider_path, provider_line = provider
    chrome_path, chrome_line = chrome
    findings.append(
        _finding(
            root_cause="post-auth-navigation-before-user-context-refresh",
            path=path,
            line_start=write_line,
            message="A login flow persists the new token and navigates before refreshing the shared user context that drives mounted chrome.",
            evidence=(
                f"Authentication completes at line {login_line}, the token is written at line {write_line}, and navigation runs at "
                f"line {nav_line}. {provider_path}:{provider_line} owns refreshUser/setUser, while {chrome_path}:{chrome_line} "
                "renders user state from that context; no awaited refreshUser call occurs before navigation."
            ),
            supporting=(
                f"{path}:{write_line}",
                f"{path}:{nav_line}",
                f"{provider_path}:{provider_line}",
                f"{chrome_path}:{chrome_line}",
            ),
            falsifiers=(
                "Checked that the flow writes an authentication/session token rather than unrelated localStorage data.",
                "Checked that a changed provider exposes refreshUser and publishes its result through setUser.",
                "Checked that changed application chrome consumes user from the same useUser context.",
                "Checked for an awaited refreshUser call between token persistence and navigation.",
            ),
            verification=(
                "Await the shared user-context refresh after persisting the token and before navigation, then prove the already-mounted "
                "navbar observes the authenticated user without reload."
            ),
            confidence=0.98,
        )
    )
    return findings


def _sticky_session_query(texts: dict[str, str]) -> tuple[str, int] | None:
    for path, text in texts.items():
        session = _SESSION_QUERY_RE.search(text)
        if session is None:
            continue
        if "@tanstack/react-query" not in text or _STICKY_QUERY_RE.search(text) is None:
            continue
        return path, _line(text, session.start())
    return None


def _session_query_navigation_findings(
    path: str,
    text: str,
    session_query: tuple[str, int],
) -> list[dict[str, Any]]:
    router_import = _NEXT_ROUTER_IMPORT_RE.search(text)
    if router_import is None:
        return []
    auth_call = re.search(
        r"await\s+(?P<method>login|registerUser|register|signIn|authenticate)\s*\(",
        text,
        re.I,
    )
    if auth_call is None:
        return []
    navigation = _ROUTER_NAV_RE.search(text, auth_call.end(), auth_call.end() + 1300)
    if navigation is None:
        return []
    between = text[auth_call.end() : navigation.start()]
    if _QUERY_SYNC_RE.search(between):
        return []
    auth_line = _line(text, auth_call.start())
    nav_line = _line(text, navigation.start())
    query_path, query_line = session_query
    return [
        _finding(
            root_cause="post-auth-navigation-before-session-query-invalidation",
            path=path,
            line_start=nav_line,
            message="An authentication mutation navigates while a sticky shared session query still owns the pre-authentication verdict.",
            evidence=(
                f"{auth_call.group('method')} completes at line {auth_line} and router.{navigation.group('method')} runs at line "
                f"{nav_line} through {router_import.group('module')}. The changed session owner at {query_path}:{query_line} uses a "
                "long-lived TanStack session query, but no invalidate/refetch/reset/clear occurs before navigation."
            ),
            supporting=(f"{path}:{auth_line}", f"{path}:{nav_line}", f"{query_path}:{query_line}"),
            falsifiers=(
                "Checked that a changed file defines a TanStack query keyed to session state.",
                "Checked that the query has sticky ownership such as staleTime, refetchOnMount false, or shared sessionQueryOptions.",
                "Checked that an explicit auth mutation completes before custom Next-style router navigation.",
                "Checked for query invalidation, refetch, reset, or clear before navigation.",
            ),
            verification=(
                "Await invalidation or refetch of the authoritative session query before navigation, then prove every shared session "
                "consumer observes the new identity without relying on mount retries."
            ),
            confidence=0.98,
        )
    ]


def run_static_js_auth_context_review(
    root: str | Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    texts: dict[str, str] = {}
    readable: list[str] = []
    findings: list[dict[str, Any]] = []

    for path in changed:
        if Path(path).suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        texts[path] = text
        readable.append(path)
        findings.extend(_next_auth_context_handoffs(path, text))

    provider = _user_context_provider(texts)
    chrome = _user_context_chrome(texts)
    if provider is not None and chrome is not None:
        for path, text in texts.items():
            findings.extend(_token_navigation_without_context_refresh(path, text, provider, chrome))

    session_query = _sticky_session_query(texts)
    if session_query is not None:
        for path, text in texts.items():
            findings.extend(_session_query_navigation_findings(path, text, session_query))

    credential_destination = run_static_credential_destination_review(root_path, changed)
    findings.extend(
        dict(item)
        for item in credential_destination.get("findings", [])
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
        "schema_version": "sergeant.static-js-auth-context-review.v2",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "static_credential_destination_review": credential_destination,
        "executed_project_code": False,
    }
