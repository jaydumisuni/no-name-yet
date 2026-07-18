"""Static JavaScript controller-epoch validation across awaited work."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".html"}
_ASYNC_RE = re.compile(
    r"(?:async\s+function\s+(?P<decl>[A-Za-z_$][\w$]*)\s*\([^)]*\)|"
    r"(?:const|let|var)\s+(?P<arrow>[A-Za-z_$][\w$]*)\s*=\s*async\s*\([^)]*\)\s*=>)\s*\{",
    re.M,
)
_AWAIT_STATEMENT_RE = re.compile(r"\bawait\b(?P<statement>[\s\S]{0,1600}?);", re.M)


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


def _functions(text: str) -> list[tuple[str, str, int]]:
    rows: list[tuple[str, str, int]] = []
    for match in _ASYNC_RE.finditer(text):
        groups = match.groupdict()
        name = groups.get("decl") or groups.get("arrow") or "anonymous"
        opening = match.end() - 1
        closing = _matching_brace(text, opening)
        if closing is None:
            continue
        rows.append((name, text[opening + 1 : closing], opening + 1))
    return rows


def _findings(path: str, text: str) -> list[dict[str, Any]]:
    shared_collections = {
        match.group("name")
        for match in re.finditer(
            r"(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*new\s+(?:Map|Set)\s*\(",
            text,
        )
    }
    findings: list[dict[str, Any]] = []
    for function_name, body, body_offset in _functions(text):
        token = re.search(
            r"(?:const|let|var)\s+(?P<token>[A-Za-z_$][\w$]*)\s*=\s*new\s+AbortController\s*\(\s*\)",
            body,
        )
        if token is None:
            continue
        token_name = token.group("token")
        owner = re.search(
            rf"(?P<owner>[A-Za-z_$][\w$]*)\s*=\s*{re.escape(token_name)}\s*;",
            body[token.end() : token.end() + 500],
        )
        if owner is None:
            continue
        owner_name = owner.group("owner")
        awaits = list(_AWAIT_STATEMENT_RE.finditer(body))
        cancellable_indexes = [
            index
            for index, item in enumerate(awaits)
            if re.search(rf"\b{re.escape(token_name)}\.signal\b", item.group("statement"))
        ]
        if not cancellable_indexes:
            continue
        first_index = cancellable_indexes[0]
        for later in awaits[first_index + 1 :]:
            if re.search(rf"\b{re.escape(token_name)}\b|\bsignal\b", later.group("statement")):
                continue
            after = body[later.end() :]
            mutation = re.search(
                r"(?P<target>[A-Za-z_$][\w$]*)\s*\.\s*(?:set|add|push)\s*\(",
                after,
            )
            if mutation is None or mutation.group("target") not in shared_collections:
                continue
            between = after[: mutation.start()]
            guard = re.search(
                rf"if\s*\(\s*{re.escape(owner_name)}\s*!==\s*{re.escape(token_name)}\s*\)\s*(?:\{{\s*)?return",
                between,
            )
            if guard is not None:
                continue
            await_line = _line(text, body_offset + later.start())
            mutation_line = _line(text, body_offset + later.end() + mutation.start())
            findings.append(
                {
                    "source": "static-js-controller-epoch-officer",
                    "officer": "Mechanic",
                    "capability": "concurrency",
                    "category": "concurrency",
                    "severity": "major",
                    "root_cause": "ownership-token-not-revalidated-after-await",
                    "path": path,
                    "line_start": await_line,
                    "line_end": await_line,
                    "evidence_ref": f"{path}:{await_line}",
                    "supporting_evidence_refs": [f"{path}:{await_line}", f"{path}:{mutation_line}"],
                    "message": "An operation publishes shared state after non-cancellable awaited work without proving it still owns the active controller epoch.",
                    "evidence": (
                        f"{function_name} installs {token_name} as {owner_name}; an earlier awaited statement uses {token_name}.signal, "
                        f"but the later await at line {await_line} does not. Shared {mutation.group('target')} is mutated at line {mutation_line} "
                        f"without comparing {owner_name} to {token_name}."
                    ),
                    "falsifiers_checked": [
                        "Checked that an earlier multiline awaited statement uses the controller signal.",
                        "Checked that the later awaited statement is not bound to that controller.",
                        "Checked for an owner-token fail-fast comparison after the later await.",
                        "Checked that the subsequent mutation targets a shared Map or Set.",
                    ],
                    "verification_test": "Revalidate the active controller/epoch immediately after every non-cancellable await and before publishing shared state.",
                    "confidence": 0.98,
                    "direct_evidence": True,
                    "admission_hint": "actionable",
                }
            )
            break
    return findings


def run_static_js_controller_epoch_review(
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
        findings.extend(_findings(path, text))
    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding["root_cause"]), str(finding["path"]), int(finding["line_start"]))] = finding
    return {
        "schema_version": "sergeant.static-js-controller-epoch-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": readable,
        "executed_project_code": False,
    }
