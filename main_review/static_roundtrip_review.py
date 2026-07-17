"""Static analysis for typed JSON read-modify-write round trips that lose fields."""

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


def run_static_roundtrip_review(root: str | Path, changed_files: Iterable[str]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    changed = sorted({str(item) for item in changed_files if str(item)})
    go_files: dict[str, str] = {}
    for path in changed:
        if Path(path).suffix.lower() != ".go":
            continue
        text = _safe_text(root_path, path)
        if text:
            go_files[path] = text

    corpus = "\n".join(go_files.values())
    findings: list[dict[str, Any]] = []
    # A server-owned document is fetched into a typed struct and later sent back
    # to the same endpoint. Unknown fields are lost unless the type preserves raw
    # members or implements custom JSON methods.
    for path, text in go_files.items():
        for match in re.finditer(
            r"(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*:=\s*&(?P<type>[A-Za-z_][A-Za-z0-9_.]*)\s*\{\}[\s\S]{0,1800}?"
            r"json\.Unmarshal\s*\([^,]+,\s*(?P=var)\s*\)",
            text,
        ):
            type_name = match.group("type")
            short_type = type_name.split(".")[-1]
            prefix = type_name.rsplit(".", 1)[0] if "." in type_name else ""
            read_region = text[max(0, match.start() - 1000): match.end() + 400]
            if not re.search(r"(?:GET|fetch|read|load).*(?:config|policy|settings)|(?:config|policy|settings).*(?:GET|fetch|read|load)", read_region, re.I | re.S):
                continue
            write_pattern = re.compile(
                rf"func\s*(?:\([^)]*\)\s*)?[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\b[A-Za-z_][A-Za-z0-9_]*\s+{re.escape(type_name)}\b[^)]*\)"
                rf"[\s\S]{{0,2200}}?(?:\"PUT\"|http\.MethodPut)[\s\S]{{0,600}}?",
                re.I,
            )
            if not write_pattern.search(corpus):
                continue
            preservation = bool(
                re.search(rf"func\s*\([^)]*\*?{re.escape(short_type)}\)\s*(?:MarshalJSON|UnmarshalJSON)\s*\(", corpus)
                or re.search(r"map\s*\[\s*string\s*\]\s*json\.RawMessage|json\.RawMessage\s+`json:", corpus)
                or re.search(r"(?:Extras|UnknownFields|RawFields|AdditionalProperties)\s+map\s*\[\s*string", corpus)
            )
            if preservation:
                continue
            # Local subset packages are especially risky: they intentionally
            # model only part of a remote document and therefore cannot roundtrip
            # unknown server-owned fields through encoding/json.
            local_subset = bool(
                prefix
                and any(
                    re.search(rf"package\s+{re.escape(prefix.split('.')[-1])}\b", candidate)
                    and re.search(rf"type\s+{re.escape(short_type)}\s+struct\s*\{{", candidate)
                    for candidate in go_files.values()
                )
            )
            if not local_subset:
                continue
            line_start = _line(text, match.start())
            findings.append({
                "source": "static-roundtrip-officer",
                "officer": "Engineer",
                "capability": "api_contract",
                "category": "api_contract",
                "severity": "major",
                "root_cause": "lossy-typed-json-roundtrip",
                "path": path,
                "line_start": line_start,
                "line_end": line_start,
                "evidence_ref": f"{path}:{line_start}",
                "message": "A server-owned JSON document is read into a subset struct and written back without preserving unknown fields.",
                "evidence": (
                    f"{type_name} is populated by json.Unmarshal from a configuration read and is later sent through a PUT path. "
                    "The local type has no custom JSON roundtrip or raw unknown-field map, so unmodelled server fields disappear on marshal."
                ),
                "falsifiers_checked": [
                    "Checked for MarshalJSON/UnmarshalJSON on the round-tripped type.",
                    "Checked for a raw unknown-field or additional-properties map.",
                    "Checked that the same typed document participates in both read and PUT paths.",
                ],
                "verification_test": (
                    "Preserve unknown members through custom JSON/raw-field storage or use a complete authoritative type, then prove GET→modify→PUT retains untouched fields."
                ),
                "confidence": 0.96,
                "direct_evidence": True,
                "admission_hint": "actionable",
            })

    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for finding in findings:
        unique[(str(finding["root_cause"]), str(finding["path"]))] = finding
    return {
        "schema_version": "sergeant.static-roundtrip-review.v1",
        "mode": "model_free_static",
        "finding_count": len(unique),
        "findings": list(unique.values()),
        "executed_project_code": False,
    }
