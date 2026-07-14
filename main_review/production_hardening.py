"""Production-hardening policies for Sergeant's public review boundary.

The rules in this module are deliberately fail-closed. They protect repository
paths, mission permissions, live GitHub endpoints, token-scope evidence, and
public output without granting Sergeant new write or execution authority.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse


class HardeningError(ValueError):
    """Raised when a production safety policy is violated."""


_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SECRET_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}=*"),
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*[^\s,;]{8,}"),
)
_SAFE_READ_SCOPES = {"read:org", "read:user", "read:packages", "read:project", "read:discussion"}
_WRITE_SCOPE_PREFIXES = ("write:", "admin:", "delete:")
_WRITE_SCOPES = {
    "repo",
    "public_repo",
    "repo:status",
    "repo_deployment",
    "workflow",
    "gist",
    "user",
    "project",
    "packages",
    "delete_repo",
}
_PERMISSION_KEYS = {"read_only", "allow_network", "allow_shell", "allow_write", "allow_untrusted_code"}
_PUBLIC_PROFILES = {"default", "public", "public-review", "pull-request-review"}
_ELEVATED_PROFILES = {"trusted-local", "internal-owner"}


def validate_repository_slug(repository: str) -> str:
    """Return a canonical ``owner/repo`` slug or fail closed."""

    value = str(repository or "").strip()
    if not _REPOSITORY_RE.fullmatch(value):
        raise HardeningError(f'repository must be a plain "owner/repo" slug, got: {value!r}')
    owner, name = value.split("/", 1)
    if owner in {".", ".."} or name in {".", ".."} or name.endswith(".git"):
        raise HardeningError(f"repository contains a forbidden path-like segment: {value!r}")
    return value


def configured_github_hosts(extra_hosts: Iterable[str] = ()) -> set[str]:
    """Return explicitly trusted GitHub API hosts."""

    env_hosts = [part.strip().lower() for part in os.getenv("SERGEANT_GITHUB_ALLOWED_HOSTS", "").split(",") if part.strip()]
    return {"api.github.com", *env_hosts, *(str(host).strip().lower() for host in extra_hosts if str(host).strip())}


def validate_github_base_url(
    base_url: str,
    *,
    allowed_hosts: Iterable[str] = (),
    allow_insecure_loopback: bool = False,
) -> str:
    """Validate a GitHub API base URL and reject SSRF-style configuration."""

    value = str(base_url or "").strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.username or parsed.password:
        raise HardeningError("GitHub API URL must not contain user information.")
    if parsed.query or parsed.fragment:
        raise HardeningError("GitHub API URL must not contain a query or fragment.")
    host = (parsed.hostname or "").lower()
    loopback = host in {"127.0.0.1", "localhost", "::1"}
    insecure_loopback = allow_insecure_loopback and parsed.scheme == "http" and loopback
    if parsed.scheme != "https" and not insecure_loopback:
        raise HardeningError("GitHub API URL must use HTTPS; HTTP is permitted only for explicitly enabled loopback tests.")
    if parsed.port not in {None, 443} and not insecure_loopback:
        raise HardeningError("GitHub API URL must use the standard HTTPS port unless an insecure loopback test is explicitly enabled.")
    if host not in configured_github_hosts(allowed_hosts) and not (allow_insecure_loopback and loopback):
        raise HardeningError(f"GitHub API host is not explicitly trusted: {host or '<missing>'}")
    allowed_paths = {"", "/", "/api/v3"}
    if parsed.path not in allowed_paths:
        raise HardeningError("GitHub API base path must be empty, '/', or '/api/v3'.")
    return value


def parse_oauth_scopes(headers: Mapping[str, Any] | None) -> set[str]:
    """Parse classic GitHub OAuth scope evidence from response headers."""

    if not headers:
        return set()
    value = ""
    for key, item in headers.items():
        if str(key).lower() == "x-oauth-scopes":
            value = str(item or "")
            break
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def assess_token_scopes(headers: Mapping[str, Any] | None, *, token_supplied: bool) -> dict[str, Any]:
    """Assess advertised token scopes and reject known write-capable scopes."""

    scopes = parse_oauth_scopes(headers)
    dangerous = sorted(
        scope
        for scope in scopes
        if scope in _WRITE_SCOPES or scope.startswith(_WRITE_SCOPE_PREFIXES) or (scope not in _SAFE_READ_SCOPES and not scope.startswith("read:"))
    )
    if dangerous:
        raise HardeningError(f"GitHub token advertises write-capable or unapproved scopes: {', '.join(dangerous)}")
    return {
        "token_supplied": bool(token_supplied),
        "advertised_scopes": sorted(scopes),
        "scope_evidence": "verified-read-only" if scopes else "not-advertised" if token_supplied else "anonymous",
        "write_scope_detected": False,
    }


def redact_secrets(value: object) -> str:
    """Redact common credential shapes from untrusted text and errors."""

    text = str(value or "")
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED_SECRET]", text)
    return text


def contains_secret(value: object) -> bool:
    """Return whether text contains a known credential shape."""

    text = str(value or "")
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def normalize_repository_path(root: str | Path, candidate: str | Path) -> str:
    """Normalize a repository-relative path and reject traversal/symlink escape."""

    raw = str(candidate or "")
    if not raw or "\x00" in raw:
        raise HardeningError("Repository path must be non-empty and contain no NUL bytes.")
    path = Path(raw)
    if path.is_absolute():
        raise HardeningError(f"Absolute repository paths are forbidden: {raw!r}")
    root_path = Path(root).resolve()
    target = (root_path / path).resolve()
    try:
        relative = target.relative_to(root_path)
    except ValueError as error:
        raise HardeningError(f"Repository path escapes the sandbox root: {raw!r}") from error
    if relative == Path("."):
        raise HardeningError("Repository file path cannot resolve to the repository root.")
    return relative.as_posix()


def normalize_input_file(root: str | Path, candidate: str | Path) -> str:
    """Normalize an explicit input file while allowing an absolute path inside root."""

    raw = str(candidate or "")
    if not raw or "\x00" in raw:
        raise HardeningError("Input file path must be non-empty and contain no NUL bytes.")
    root_path = Path(root).resolve()
    candidate_path = Path(raw)
    target = candidate_path.resolve() if candidate_path.is_absolute() else (root_path / candidate_path).resolve()
    try:
        target.relative_to(root_path)
    except ValueError as error:
        raise HardeningError(f"Input file escapes the repository root: {raw!r}") from error
    if target == root_path:
        raise HardeningError("Input file path cannot resolve to the repository root.")
    return str(target)


def normalize_changed_files(root: str | Path, changed_files: Iterable[object], *, limit: int = 2000) -> list[str]:
    """Normalize and bound changed-file input supplied by external callers."""

    output: list[str] = []
    for item in changed_files:
        path = normalize_repository_path(root, str(item))
        if path not in output:
            output.append(path)
        if len(output) > limit:
            raise HardeningError(f"Changed-file list exceeds the safety limit of {limit} entries.")
    return output


def enforce_mission_permissions(policy_profile: str, requested: Mapping[str, Any] | None) -> dict[str, bool]:
    """Apply a fail-closed permission profile to a mission request."""

    profile = str(policy_profile or "default").strip().lower()
    if profile not in _PUBLIC_PROFILES | _ELEVATED_PROFILES:
        raise HardeningError(f"Unknown policy profile: {profile!r}")
    supplied = dict(requested or {})
    unknown = sorted(set(supplied) - _PERMISSION_KEYS)
    if unknown:
        raise HardeningError(f"Unknown execution permission keys: {', '.join(unknown)}")
    permissions = {
        "read_only": bool(supplied.get("read_only", True)),
        "allow_network": bool(supplied.get("allow_network", False)),
        "allow_shell": bool(supplied.get("allow_shell", False)),
        "allow_write": bool(supplied.get("allow_write", False)),
        "allow_untrusted_code": bool(supplied.get("allow_untrusted_code", False)),
    }
    if profile in _PUBLIC_PROFILES:
        forbidden = [key for key in ("allow_shell", "allow_write", "allow_untrusted_code") if permissions[key]]
        if forbidden or not permissions["read_only"]:
            raise HardeningError(f"Public review profiles cannot elevate execution permissions: {', '.join(forbidden or ['read_only=false'])}")
        return permissions
    if os.getenv("SERGEANT_ALLOW_ELEVATED_MISSIONS", "").strip().lower() not in {"1", "true", "yes", "on"}:
        raise HardeningError("Elevated mission profile requires SERGEANT_ALLOW_ELEVATED_MISSIONS=true.")
    if permissions["allow_untrusted_code"]:
        raise HardeningError("Sergeant never executes pull-request-controlled code, including elevated local profiles.")
    if permissions["allow_write"]:
        raise HardeningError("Sergeant's reviewer runtime does not grant repository write authority.")
    permissions["read_only"] = True
    return permissions


def normalize_time_budget(value: Mapping[str, Any] | None) -> dict[str, int]:
    """Clamp mission time budgets to a bounded production range."""

    supplied = dict(value or {})
    unknown = sorted(set(supplied) - {"seconds"})
    if unknown:
        raise HardeningError(f"Unknown time-budget keys: {', '.join(unknown)}")
    try:
        seconds = int(supplied.get("seconds", 120))
    except (TypeError, ValueError) as error:
        raise HardeningError("Mission time budget must be an integer number of seconds.") from error
    if not 1 <= seconds <= 600:
        raise HardeningError("Mission time budget must be between 1 and 600 seconds.")
    return {"seconds": seconds}
