"""Static checks learned only after transfer set 14's blind 0/3 was frozen."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_SCRIPT_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}
_GO_SUFFIXES = {".go"}
_PYTHON_SUFFIXES = {".py"}


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
        if char in {'"', "'", "`"}:
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
    category: str,
    message: str,
    evidence: str,
    falsifiers: Iterable[str],
    verification: str,
    supporting: Iterable[str] = (),
    confidence: float = 0.97,
) -> dict[str, Any]:
    refs = [f"{path}:{line_start}", *[str(item) for item in supporting]]
    return {
        "source": "static-transfer-14-officer",
        "officer": "Mechanic" if category == "concurrency" else "Engineer",
        "capability": category,
        "category": category,
        "severity": "major",
        "root_cause": root_cause,
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": f"{path}:{line_start}",
        "supporting_evidence_refs": list(dict.fromkeys(refs)),
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": list(falsifiers),
        "verification_test": verification,
        "confidence": confidence,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def _python_synthetic_measurement_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() not in _PYTHON_SUFFIXES:
        return []

    findings: list[dict[str, Any]] = []
    table_re = re.compile(
        r"(?m)^(?P<table>[A-Z][A-Z0-9_]*(?:PRICE|PRICES|PRICING|COST|COSTS|RATE|RATES|TARIFF)[A-Z0-9_]*)"
        r"\s*(?::[^=\n]+)?=\s*\{"
    )
    for table in table_re.finditer(text):
        table_name = table.group("table")
        opening = text.find("{", table.start())
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        literal = text[opening : closing + 1]
        default_entry = re.search(
            r"[\"'](?:default|fallback|unknown)[\"']\s*:\s*\{(?P<body>[\s\S]{0,500}?)\}",
            literal,
            re.I,
        )
        if default_entry is None or re.search(r"[-+]?\d+(?:\.\d+)?", default_entry.group("body")) is None:
            continue

        lookup_re = re.compile(
            rf"\b{re.escape(table_name)}\.get\s*\("
            rf"(?P<selector>[^,\n]+),\s*{re.escape(table_name)}\s*\[\s*[\"'](?:default|fallback|unknown)[\"']\s*\]\s*\)"
        )
        for lookup in lookup_re.finditer(text, closing + 1):
            before = text[max(closing + 1, lookup.start() - 1500) : lookup.start()]
            function_header = re.search(
                r"def\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*(?:->\s*[^:]+)?\s*:\s*$",
                before,
                re.M,
            )
            if function_header is None:
                continue
            function_name = function_header.group("name")
            if re.search(r"(?:cost|price|rate|charge|bill|estimate|value)", function_name, re.I) is None:
                continue
            window = text[lookup.start() : min(len(text), lookup.start() + 1200)]
            if re.search(r"(?:unknown|unavailable|None|not\s+priced)", window, re.I):
                continue
            line = _line(text, lookup.start())
            findings.append(
                _finding(
                    root_cause="unknown-external-entity-assigned-synthetic-measurement",
                    path=path,
                    line_start=line,
                    category="data_integrity",
                    message="An unknown external entity is assigned a plausible synthetic measurement instead of remaining explicitly unknown.",
                    evidence=(
                        f"`{function_name}` resolves an unmatched selector through `{table_name}`'s numeric default entry. "
                        "The returned cost/rate is indistinguishable from a supported, sourced measurement."
                    ),
                    falsifiers=(
                        "Checked that the table name and consuming function describe pricing, cost, rate, billing, or value measurement.",
                        "Checked that the fallback entry contains numeric measurement values.",
                        "Checked that an unmatched lookup directly borrows that fallback rather than returning an explicit unknown/unavailable state.",
                    ),
                    verification=(
                        "Return an explicit unknown result for unmatched identifiers, attach provenance to known measurements, and prove downstream gates "
                        "do not compare or present incomplete values as exact."
                    ),
                )
            )
    return findings


def _script_exact_proxy_policy_findings(path: str, text: str) -> list[dict[str, Any]]:
    if Path(path).suffix.lower() not in _SCRIPT_SUFFIXES:
        return []
    if re.search(r"(?:universal|generic)\s+(?:action\s+)?proxy", text, re.I) is None:
        return []
    if re.search(r"await\s+[^;\n]*\.json\s*\(\s*\)", text) is None:
        return []
    if re.search(r"fetch\s*\(\s*`[^`]*\$\{\s*(?:path|route|endpoint)\s*\}", text, re.I) is None:
        return []

    set_match = re.search(
        r"const\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*(?:PATH|ROUTE|ENDPOINT)[A-Za-z0-9_$]*)"
        r"\s*=\s*new\s+Set(?:<[^>]+>)?\s*\(\s*\[(?P<body>[\s\S]{0,5000}?)\]\s*\)",
        text,
        re.I,
    )
    if set_match is None:
        return []
    if re.search(r"(?:static[- ]only|only\s+static\s+routes)", text[max(0, set_match.start() - 500) : set_match.start()], re.I):
        return []
    literals = re.findall(r"[\"'](/api/[^\"']+)[\"']", set_match.group("body"))
    if len(literals) < 2:
        return []
    policy_name = set_match.group("name")
    has_match = re.search(rf"\b{re.escape(policy_name)}\.has\s*\(\s*(?:path|route|endpoint)\s*\)", text, re.I)
    if has_match is None:
        return []
    if re.search(r"(?:RegExp|\.test\s*\(|match\s*\(|path-to-regexp|URLPattern)", text):
        return []

    line = _line(text, has_match.start())
    return [
        _finding(
            root_cause="generic-proxy-exact-path-policy-cannot-authorize-parameterized-routes",
            path=path,
            line_start=line,
            category="api_contract",
            message="A generic action proxy authorizes routes only by exact-string membership and cannot represent resource-scoped path families.",
            evidence=(
                f"The request body supplies a path that is forwarded through a generic proxy, but `{policy_name}.has(path)` accepts only "
                f"the {len(literals)} literal strings declared in the file. Parameterized routes such as resource IDs or names have no representable policy form."
            ),
            falsifiers=(
                "Checked that the handler is explicitly a universal or generic proxy, not a fixed single-endpoint adapter.",
                "Checked that the caller supplies the forwarded path through parsed request data.",
                "Checked that authorization is exact Set membership with no regex, URLPattern, route matcher, or equivalent dynamic pattern layer.",
                "Excluded proxies explicitly documented as static-route-only.",
            ),
            verification=(
                "Represent authorized route families with anchored patterns or a typed route table, reject dot-segment/path-normalization bypasses, "
                "and test every real caller path plus hostile near-misses."
            ),
        )
    ]


def _go_functions(path: str, text: str) -> list[tuple[str, str, int, str]]:
    functions: list[tuple[str, str, int, str]] = []
    pattern = re.compile(
        r"\bfunc\s*(?:\([^)]*\)\s*)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
        r"\s*\([^)]*\)(?:\s*\([^)]*\)|\s+[^\{\n]+)?\s*\{",
        re.M,
    )
    for match in pattern.finditer(text):
        opening = match.end() - 1
        closing = _matching_brace(text, opening)
        if closing is not None:
            functions.append((match.group("name"), text[opening + 1 : closing], match.start(), path))
    return functions


def _go_cache_generation_findings(texts: dict[str, str]) -> list[dict[str, Any]]:
    functions: list[tuple[str, str, int, str]] = []
    for path, text in texts.items():
        if Path(path).suffix.lower() in _GO_SUFFIXES:
            functions.extend(_go_functions(path, text))

    read_paths: list[tuple[str, str, int, str]] = []
    invalidators: list[tuple[str, str, int, str]] = []
    for name, body, offset, path in functions:
        authoritative_read = re.search(r"\b(?:store|repo|repository|source|backend)\.Get\s*\(", body, re.I)
        cache_write = re.search(
            r"\b(?:cacheSet|setCache|writeCache|putCache)\s*\(|\b(?:cache|cacheStore|links)\.Set\s*\(",
            body,
            re.I,
        )
        if authoritative_read and cache_write and authoritative_read.start() < cache_write.start():
            read_paths.append((name, body, offset, path))

        cache_delete = re.search(
            r"\b(?:invalidateCache|evictCache|deleteCache)\s*\(|\b(?:cache|cacheStore|links)\.Delete\s*\(",
            body,
            re.I,
        )
        if cache_delete and re.search(r"(?:invalidate|evict|delete|deactivate|activate|mutate|update)", name, re.I):
            invalidators.append((name, body, offset, path))

    if not read_paths or not invalidators:
        return []

    corpus = "\n".join(texts.values())
    has_generation_guard = bool(
        re.search(r"(?:cache|entry)?(?:Gen|Generation|Version|Epoch)\s*\.\s*(?:Load|Add|Compare|Swap)", corpus)
        and re.search(r"(?:!=|==)\s*(?:gen|generation|version|epoch)|(?:gen|generation|version|epoch)\s*(?:!=|==)", corpus, re.I)
    )
    has_shared_exclusion = bool(
        re.search(r"(?:cache|lookup|resolve)[A-Za-z0-9_]*Mu\.(?:R?Lock)\s*\(", corpus, re.I)
        and re.search(r"(?:invalidate|delete|mutate)[\s\S]{0,800}?(?:cache|lookup|resolve)[A-Za-z0-9_]*Mu\.Lock\s*\(", corpus, re.I)
    )
    if has_generation_guard or has_shared_exclusion:
        return []

    findings: list[dict[str, Any]] = []
    supporting = [f"{path}:{_line(texts[path], offset)}" for _, _, offset, path in invalidators]
    for name, _, offset, path in read_paths:
        line = _line(texts[path], offset)
        findings.append(
            _finding(
                root_cause="read-through-cache-writeback-not-ordered-with-invalidation",
                path=path,
                line_start=line,
                category="concurrency",
                message="A read-through cache fill can publish an authoritative snapshot after a concurrent invalidation has already completed.",
                evidence=(
                    f"`{name}` reads from the authoritative store and later writes that snapshot into cache, while a lifecycle path deletes the cache entry. "
                    "No shared generation/epoch check or exclusion boundary orders the late write-back against invalidation, so stale state can be resurrected."
                ),
                falsifiers=(
                    "Checked that the read path performs an authoritative Get before a cache Set/write-back.",
                    "Checked that a lifecycle or mutation path can evict the same cache family.",
                    "Checked the changed-file corpus for a generation/version/epoch snapshot-and-compare guard.",
                    "Checked for a shared lock ordering cache fill and invalidation.",
                ),
                verification=(
                    "Snapshot a cache generation before the authoritative read and reject/evict the fill if invalidation advanced it, or serialize both operations "
                    "through one keyed exclusion boundary; test delete/recreate or mutate races deterministically."
                ),
                supporting=supporting,
            )
        )
    return findings


def run_static_transfer_14_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    texts: dict[str, str] = {}
    readable: list[str] = []
    findings: list[dict[str, Any]] = []

    for path in changed:
        text = _safe_text(root_path, path)
        if not text:
            continue
        texts[path] = text
        readable.append(path)
        findings.extend(_python_synthetic_measurement_findings(path, text))
        findings.extend(_script_exact_proxy_policy_findings(path, text))

    findings.extend(_go_cache_generation_findings(texts))

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[
            (
                str(finding.get("root_cause")),
                str(finding.get("path")),
                int(finding.get("line_start") or 0),
            )
        ] = finding
    return {
        "schema_version": "sergeant.static-transfer-14-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
