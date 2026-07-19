"""Static checks for caller-supplied ownership on authenticated resource reads."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_CLIENT_SUFFIXES = {".dart", ".js", ".jsx", ".ts", ".tsx", ".kt", ".kts", ".swift"}
_SERVER_SUFFIXES = {".php", ".py", ".js", ".ts", ".go", ".rb"}
_RESOURCE_RE = re.compile(r"(?:wallet|ledger|statement|balance|account|profile|orders?)", re.I)
_OWNER_RE = re.compile(r"(?:\$\{?\s*)?(?:user|owner|account|customer)[A-Za-z0-9_]*[Ii]d\b", re.I)
_AUTH_ROUTE_RE = re.compile(
    r"Route::(?:get|post)\s*\(\s*[\"'](?P<route>[^\"']+)[\"'][^\n]{0,400}middleware\s*\(\s*[\"'][^\"']*auth",
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


def _authenticated_ownerless_resources(texts: dict[str, str]) -> dict[str, tuple[str, int, str]]:
    result: dict[str, tuple[str, int, str]] = {}
    for path, text in texts.items():
        if Path(path).suffix.lower() not in _SERVER_SUFFIXES:
            continue
        for match in _AUTH_ROUTE_RE.finditer(text):
            route = match.group("route")
            if re.search(r"\{[^}]+\}", route):
                continue
            resource = _RESOURCE_RE.search(route)
            if resource is None:
                continue
            result[resource.group(0).lower()] = (path, _line(text, match.start()), route)
    return result


def _finding(
    client_path: str,
    client_line: int,
    resource: str,
    route_path: str,
    route_line: int,
    route: str,
) -> dict[str, Any]:
    return {
        "source": "static-authenticated-owner-officer",
        "officer": "Mechanic",
        "capability": "authorization",
        "category": "authorization",
        "severity": "major",
        "root_cause": "authenticated-resource-read-uses-caller-owner-id",
        "path": client_path,
        "line_start": client_line,
        "line_end": client_line,
        "evidence_ref": f"{client_path}:{client_line}",
        "supporting_evidence_refs": [f"{client_path}:{client_line}", f"{route_path}:{route_line}"],
        "message": "An authenticated customer-resource read places a caller-supplied owner identifier in the request path.",
        "evidence": (
            f"The client addresses {resource} data with a user/owner/account ID at line {client_line}, while the changed server contract "
            f"already exposes authenticated owner-derived route {route!r} at {route_path}:{route_line}. Caller-controlled ownership can "
            "select another principal or preserve an insecure legacy path."
        ),
        "falsifiers_checked": [
            "Checked that the resource is customer-owned or account-scoped.",
            "Checked that the client URL interpolates a user/owner/account/customer identifier.",
            "Checked for an authenticated route for the same resource without an owner path parameter.",
            "Checked that the authenticated route itself does not require a caller owner identifier.",
        ],
        "verification_test": (
            "Read ownership exclusively from the authenticated principal, remove owner IDs from customer-facing route paths, and prove "
            "a caller cannot request another customer's balance, wallet, statement, account or order data."
        ),
        "confidence": 0.98,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def run_static_authenticated_owner_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    texts = {path: _safe_text(root_path, path) for path in changed}
    texts = {path: text for path, text in texts.items() if text}
    ownerless = _authenticated_ownerless_resources(texts)
    findings: list[dict[str, Any]] = []

    for path, text in texts.items():
        if Path(path).suffix.lower() not in _CLIENT_SUFFIXES:
            continue
        for request in re.finditer(r"(?:get|post|put|patch|delete)\s*\(\s*[\"'](?P<url>[^\"']+)[\"']", text, re.I):
            url = request.group("url")
            owner = _OWNER_RE.search(url)
            resource_match = _RESOURCE_RE.search(url)
            if owner is None or resource_match is None:
                continue
            resource = resource_match.group(0).lower()
            route_row = ownerless.get(resource)
            if route_row is None and resource.endswith("s"):
                route_row = ownerless.get(resource[:-1])
            if route_row is None:
                continue
            route_path, route_line, route = route_row
            findings.append(
                _finding(path, _line(text, request.start()), resource, route_path, route_line, route)
            )
            break

    unique = {(str(item["root_cause"]), str(item["path"])): item for item in findings}
    return {
        "schema_version": "sergeant.static-authenticated-owner-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "authenticated_ownerless_resources": ownerless,
        "executed_project_code": False,
    }
