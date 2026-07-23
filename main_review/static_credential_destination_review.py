"""Model-free credential destination boundary review.

The officer looks for code that attaches bearer or authorization credentials to an
outgoing request after only broad host-category or path-prefix checks.  A valid
boundary must bind the request to the exact configured trusted origin (scheme,
host, and port) before the credential sink is reached.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable


_SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py"}
_CREDENTIAL_SINKS = (
    re.compile(
        r"(?:headers?|requestHeaders?|options?\.headers)\s*\.\s*set\s*\(\s*[\"']Authorization[\"']\s*,[^\n;]{0,400}(?:Bearer|token|api[_-]?key|credential|secret)",
        re.I,
    ),
    re.compile(
        r"(?:headers?|request_headers?|options?\.headers)\s*(?:\[[\"']Authorization[\"']\]|\.Authorization)\s*=\s*[^\n;]{0,400}(?:Bearer|token|api[_-]?key|credential|secret)",
        re.I,
    ),
    re.compile(
        r"[\"']?Authorization[\"']?\s*:\s*[^,}\n]{0,400}(?:Bearer|token|api[_-]?key|credential|secret)",
        re.I,
    ),
    re.compile(
        r"(?:headers?|session\.headers)\.update\s*\(\s*\{[^}]{0,500}[\"']Authorization[\"']\s*:\s*[^}]{0,300}(?:Bearer|token|api[_-]?key|credential|secret)",
        re.I | re.S,
    ),
)
_BROAD_DESTINATION_CHECKS = (
    re.compile(r"\.(?:hostname|host|netloc)\b", re.I),
    re.compile(r"\.(?:pathname|path)\s*\.\s*(?:startsWith|includes|indexOf)\s*\(", re.I),
    re.compile(r"\.(?:path|hostname)\.startswith\s*\(", re.I),
    re.compile(r"\b(?:loopback|localhost|trustedHosts?|allowedHosts?|hostAllowlist)\b", re.I),
)
_EXACT_JS_ORIGIN = (
    re.compile(r"\.origin\s*(?:===|!==|==|!=)\s*[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*\.origin\b", re.I),
    re.compile(r"\.origin\s*(?:===|!==|==|!=)\s*[A-Za-z_$][\w$]*(?:Origin|origin)\b", re.I),
    re.compile(r"[A-Za-z_$][\w$]*(?:Origin|origin)\s*(?:===|!==|==|!=)\s*[A-Za-z_$][\w$]*\.origin\b", re.I),
    re.compile(r"new\s+URL\s*\([^)]*(?:server|base|endpoint|origin|configured|trusted)[^)]*\)\.origin", re.I),
)
_EXACT_PYTHON_ORIGIN = (
    re.compile(r"(?:request|target|parsed|url)[A-Za-z0-9_]*_?origin\s*(?:==|!=)\s*(?:trusted|configured|server|base)[A-Za-z0-9_]*_?origin", re.I),
    re.compile(r"\(\s*[A-Za-z_][\w]*\.scheme\s*,\s*[A-Za-z_][\w]*\.(?:netloc|hostname)\s*\)\s*(?:==|!=)\s*\(\s*[A-Za-z_][\w]*\.scheme\s*,\s*[A-Za-z_][\w]*\.(?:netloc|hostname)\s*\)", re.I),
    re.compile(r"f?[\"']\{?[A-Za-z_][\w]*\.scheme\}?://\{?[A-Za-z_][\w]*\.(?:netloc|hostname)\}?[\"']\s*(?:==|!=)\s*(?:trusted|configured|server|base)[A-Za-z0-9_]*_?origin", re.I),
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


def _first(patterns: Iterable[re.Pattern[str]], text: str) -> re.Match[str] | None:
    matches = [match for pattern in patterns if (match := pattern.search(text)) is not None]
    return min(matches, key=lambda match: match.start()) if matches else None


def _has_exact_destination_binding(text: str, suffix: str) -> bool:
    patterns = _EXACT_PYTHON_ORIGIN if suffix == ".py" else _EXACT_JS_ORIGIN
    if any(pattern.search(text) for pattern in patterns):
        return True
    if suffix != ".py":
        fields = {
            field
            for field in ("protocol", "hostname", "port")
            if re.search(rf"\.{field}\s*(?:===|!==|==|!=)", text, re.I)
        }
        return fields == {"protocol", "hostname", "port"}
    return False


def _credential_destination_findings(path: str, text: str) -> list[dict[str, Any]]:
    suffix = Path(path).suffix.lower()
    sink = _first(_CREDENTIAL_SINKS, text)
    if sink is None:
        return []
    broad = _first(_BROAD_DESTINATION_CHECKS, text)
    if broad is None or _has_exact_destination_binding(text, suffix):
        return []

    sink_line = _line(text, sink.start())
    broad_line = _line(text, broad.start())
    return [
        {
            "source": "static-credential-destination-officer",
            "officer": "Medic",
            "capability": "security_taint",
            "category": "security_taint",
            "severity": "major",
            "root_cause": "credential-attached-without-exact-destination-binding",
            "path": path,
            "line_start": sink_line,
            "line_end": sink_line,
            "evidence_ref": f"{path}:{sink_line}",
            "supporting_evidence_refs": [f"{path}:{broad_line}", f"{path}:{sink_line}"],
            "message": "An outgoing request receives an authorization credential after only a broad host or path check, without binding the request to the exact configured trusted origin.",
            "evidence": (
                f"A broad destination test appears at line {broad_line}, while an Authorization credential sink appears at line "
                f"{sink_line}. No exact scheme+host+port origin comparison to configured trust was found before credential attachment."
            ),
            "falsifiers_checked": [
                "Checked for an exact URL.origin comparison against a configured trusted origin.",
                "Checked for explicit protocol, hostname, and port equality.",
                "Checked for Python scheme/netloc tuple equality or an equivalent configured-origin comparison.",
                "Required both a broad destination check and a credential-bearing Authorization sink.",
            ],
            "verification_test": (
                "Parse both the request destination and configured trusted endpoint, require exact origin equality before attaching "
                "credentials, preserve an existing Authorization header, and prove wrong scheme, port, subdomain, IPv4/IPv6 alias, "
                "redirect destination, malformed configuration, and non-API paths remain credential-free."
            ),
            "confidence": 0.96,
            "direct_evidence": True,
            "admission_hint": "actionable",
        }
    ]


def run_static_credential_destination_review(
    root: str | Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    readable: list[str] = []
    findings: list[dict[str, Any]] = []
    for path in changed:
        if Path(path).suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        readable.append(path)
        findings.extend(_credential_destination_findings(path, text))

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
        "schema_version": "sergeant.static-credential-destination-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
