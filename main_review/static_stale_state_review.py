"""Brace-aware static analysis for persisted failure states that never self-heal."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable


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


def _go_functions(text: str) -> list[tuple[str, str, int]]:
    functions: list[tuple[str, str, int]] = []
    pattern = re.compile(
        r"func\s*(?:\([^)]*\)\s*)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*(?:\([^)]*\)|[^\{\n]+)?\{",
        re.M,
    )
    for match in pattern.finditer(text):
        opening = match.end() - 1
        closing = _matching_brace(text, opening)
        if closing is not None:
            functions.append((match.group("name"), text[opening + 1 : closing], opening + 1))
    return functions


def _else_body_for_flag(body: str, flag: str, start: int) -> tuple[str, int] | None:
    branch = re.search(rf"\bif\s+{re.escape(flag)}\s*\{{", body[start:])
    if branch is None:
        return None
    if_start = start + branch.start()
    if_open = start + branch.end() - 1
    if_close = _matching_brace(body, if_open)
    if if_close is None:
        return None
    else_match = re.match(r"\s*else\s*\{", body[if_close + 1 :])
    if else_match is None:
        return None
    else_open = if_close + 1 + else_match.end() - 1
    else_close = _matching_brace(body, else_open)
    if else_close is None:
        return None
    return body[else_open + 1 : else_close], if_start


def run_static_stale_state_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    findings: list[dict[str, Any]] = []

    for path in changed:
        if Path(path).suffix.lower() != ".go":
            continue
        text = _safe_text(root_path, path)
        if not text:
            continue
        for function_name, body, body_offset in _go_functions(text):
            failed_fields = {
                match.group("field")
                for match in re.finditer(
                    r"Status\.(?P<field>[A-Za-z0-9_]*Status)\s*=\s*[A-Za-z0-9_.]*Failed",
                    body,
                )
            }
            if not failed_fields:
                continue
            for calculation in re.finditer(
                r"(?P<changed>[A-Za-z_][A-Za-z0-9_]*)\s*,\s*(?P<new>[A-Za-z_][A-Za-z0-9_]*)\s*:=\s*[^\n]*(?:Change|Diff|Calculate)[A-Za-z0-9_]*\s*\(",
                body,
                re.I,
            ):
                alternate = _else_body_for_flag(body, calculation.group("changed"), calculation.end())
                if alternate is None:
                    continue
                else_body, branch_offset = alternate
                for field in failed_fields:
                    empty_check = re.search(
                        rf"Status\.{re.escape(field)}\s*==\s*[\"']{{2}}",
                        else_body,
                    )
                    success_write = re.search(
                        rf"Status\.{re.escape(field)}\s*=\s*[A-Za-z0-9_.]*(?:Complete|Ready|Healthy|Success)",
                        else_body,
                    )
                    if empty_check is None or success_write is None:
                        continue
                    handles_failed = re.search(
                        rf"Status\.{re.escape(field)}\s*==\s*[A-Za-z0-9_.]*Failed",
                        else_body,
                    )
                    if handles_failed is not None:
                        continue
                    findings.append(
                        {
                            "source": "static-stale-state-officer",
                            "officer": "Mechanic",
                            "capability": "state_lifecycle",
                            "category": "state_lifecycle",
                            "severity": "major",
                            "root_cause": "persisted-failure-not-recovered",
                            "path": path,
                            "line_start": _line(text, body_offset + branch_offset),
                            "line_end": _line(text, body_offset + branch_offset),
                            "evidence_ref": f"{path}:{_line(text, body_offset + branch_offset)}",
                            "message": "A previously persisted failed status is not cleared after the underlying operation succeeds with no calculated changes.",
                            "evidence": (
                                f"{function_name} can persist Failed in Status.{field}. Its brace-matched no-change branch "
                                "promotes only an empty status to the successful terminal state, so a recovered provider "
                                "with unchanged desired state leaves the old failure sticky."
                            ),
                            "falsifiers_checked": [
                                "Checked the complete brace-matched no-change branch rather than a fixed text window.",
                                "Checked whether the branch also accepts the failed terminal state.",
                                "Checked that the same function can persist the failed state earlier.",
                            ],
                            "verification_test": (
                                "On a successful no-change reconcile, promote both empty and transient-failed state to the "
                                "healthy terminal state and clear the persisted error."
                            ),
                            "confidence": 0.97,
                            "direct_evidence": True,
                            "admission_hint": "actionable",
                        }
                    )
                    break

    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding["root_cause"]), str(finding["path"]))] = finding
    return {
        "schema_version": "sergeant.static-stale-state-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "executed_project_code": False,
    }
