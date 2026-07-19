"""Static review for defaults resolved in presentation but lost before execution."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

_GO_SUFFIXES = {".go"}
_SELECTOR_FIELDS = ("Model", "Provider", "Backend", "Profile", "Engine", "Runtime")


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
) -> dict[str, Any]:
    refs = [f"{path}:{line_start}", *[str(item) for item in supporting]]
    return {
        "source": "static-selector-continuity-officer",
        "officer": "Engineer",
        "capability": "architecture",
        "category": "architecture",
        "severity": "major",
        "root_cause": root_cause,
        "path": path,
        "line_start": line_start,
        "line_end": line_start,
        "evidence_ref": f"{path}:{line_start}",
        "supporting_evidence_refs": list(dict.fromkeys(refs)),
        "message": message,
        "evidence": evidence,
        "falsifiers_checked": [
            "Checked that the presentation path resolves and displays a selector-like default.",
            "Checked that the bridge/adapter constructor receives only the execution authority and no corresponding default selector.",
            "Checked that operation creation forwards the caller selector directly without an empty-value fallback.",
        ],
        "verification_test": (
            "Resolve one authoritative default, pass it into both presentation and execution adapters, and prove an empty create option uses the same value the operator sees."
        ),
        "confidence": 0.97,
        "direct_evidence": True,
        "admission_hint": "actionable",
    }


def _selector_continuity_findings(texts: dict[str, str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    for field in _SELECTOR_FIELDS:
        presentation: tuple[str, str, re.Match[str], re.Match[str]] | None = None
        bridge: tuple[str, str, re.Match[str], re.Match[str]] | None = None

        for path, text in texts.items():
            displayed = re.search(
                rf"\b{re.escape(field)}\s*:\s*(?P<resolver>resolve[A-Za-z0-9_]*{re.escape(field)}\s*\([^)]*\))",
                text,
                re.I,
            )
            one_arg_bridge = re.search(
                r"\b(?P<pkg>[A-Za-z_][A-Za-z0-9_]*(?:bridge|adapter)[A-Za-z0-9_]*)\.New"
                r"\s*\(\s*[A-Za-z_][A-Za-z0-9_]*\s*\)",
                text,
                re.I,
            )
            if displayed is not None and one_arg_bridge is not None:
                presentation = (path, text, displayed, one_arg_bridge)

            constructor = re.search(
                r"func\s+New\s*\(\s*[A-Za-z_][A-Za-z0-9_]*\s+\*[^,)]*\)\s+"
                r"(?P<adapter>[A-Za-z_][A-Za-z0-9_]*)\s*\{",
                text,
            )
            create = re.search(
                rf"func\s*\([^)]*\)\s*Create\s*\([^)]*opts\s+[A-Za-z0-9_.]*CreateOptions[^)]*\)"
                rf"[\s\S]{{0,1800}}?CreateOptions\s*\{{[\s\S]{{0,700}}?"
                rf"{re.escape(field)}\s*:\s*opts\.{re.escape(field)}\b",
                text,
            )
            has_default_storage = re.search(
                rf"\bdefault{re.escape(field)}\b|\b{re.escape(field.lower())}Default\b",
                text,
                re.I,
            )
            has_fallback = re.search(
                rf"if\s+opts\.{re.escape(field)}\s*==\s*\"\"[\s\S]{{0,300}}?opts\.{re.escape(field)}\s*=",
                text,
            )
            if constructor is not None and create is not None and has_default_storage is None and has_fallback is None:
                bridge = (path, text, constructor, create)

        if presentation is None or bridge is None:
            continue

        presentation_path, presentation_text, displayed, one_arg_bridge = presentation
        bridge_path, bridge_text, constructor, create = bridge
        findings.append(
            _finding(
                root_cause="resolved-display-default-not-propagated-to-operation-create",
                path=presentation_path,
                line_start=_line(presentation_text, one_arg_bridge.start()),
                message=(
                    f"A default {field.lower()} is resolved for presentation but not propagated through the adapter that creates the operation."
                ),
                evidence=(
                    f"`{presentation_path}` resolves `{displayed.group('resolver')}` into the displayed `{field}` but constructs the bridge with one argument. "
                    f"`{bridge_path}` stores no default `{field}` and forwards only `opts.{field}`, so an empty create option can reach execution while the UI displays a resolved value."
                ),
                supporting=(
                    f"{presentation_path}:{_line(presentation_text, displayed.start())}",
                    f"{bridge_path}:{_line(bridge_text, constructor.start())}",
                    f"{bridge_path}:{_line(bridge_text, create.start())}",
                ),
            )
        )

    return findings


def run_static_selector_continuity_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    texts: dict[str, str] = {}
    for path in changed:
        if Path(path).suffix.lower() not in _GO_SUFFIXES:
            continue
        text = _safe_text(root_path, path)
        if text:
            texts[path] = text

    findings = _selector_continuity_findings(texts)
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding["root_cause"]), str(finding["path"]))] = finding

    return {
        "schema_version": "sergeant.static-selector-continuity-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "readable_changed_files": sorted(texts),
        "executed_project_code": False,
    }
