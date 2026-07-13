"""Policy normalization for Tier 1 capability findings.

Capability scanners intentionally over-collect signals. This policy layer
separates blast radius and lexical co-presence from demonstrated defects before
those findings enter review intelligence and consensus.
"""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any

IMPACT_ONLY_CAPABILITIES = {"call_graph", "cross_file"}
DEMONSTRATED_SECURITY_SINK_RE = re.compile(
    r"(?:\beval\s*\(|\bexec\s*\(|\bos\.system\s*\(|\bsubprocess\.|"
    r"\bchild_process\.exec\s*\(|\bcp\.exec\s*\(|\bquery\s*\(|\braw\s*\(|"
    r"\binnerHTML\b|\bdangerouslySetInnerHTML\b|\bshell\s*:\s*true\b)",
    re.I,
)


def _safe_text(root: Path | None, relative: object) -> str:
    if root is None or not isinstance(relative, str) or not relative:
        return ""
    try:
        resolved_root = root.resolve()
        path = (resolved_root / relative).resolve()
        if not path.is_relative_to(resolved_root) or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def normalize_capability_review(
    packet: dict[str, Any],
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Return a capability packet with evidence-aware blocking severity."""

    normalized = deepcopy(packet)
    raw_findings = normalized.get("findings", [])
    findings = raw_findings if isinstance(raw_findings, list) else []
    adjustments: list[dict[str, object]] = []
    root_path = Path(root) if root is not None else None

    for finding in findings:
        if not isinstance(finding, dict):
            continue
        capability = str(finding.get("capability", ""))
        severity = str(finding.get("severity", ""))

        if capability in IMPACT_ONLY_CAPABILITIES and severity in {"blocker", "major"}:
            adjustments.append(
                {
                    "capability": capability,
                    "path": finding.get("path"),
                    "from": severity,
                    "to": "minor",
                    "reason": "Dependency or caller presence is blast-radius evidence, not a demonstrated defect.",
                }
            )
            finding["severity"] = "minor"
            finding["impact_signal"] = True
            continue

        if capability == "security_taint" and severity in {"blocker", "major"}:
            text = _safe_text(root_path, finding.get("path"))
            if text and not DEMONSTRATED_SECURITY_SINK_RE.search(text):
                adjustments.append(
                    {
                        "capability": capability,
                        "path": finding.get("path"),
                        "from": severity,
                        "to": "note",
                        "reason": "Input and security-related words co-occur, but no executable sensitive sink was demonstrated.",
                    }
                )
                finding["severity"] = "note"
                finding["lexical_signal"] = True
                finding["message"] = "Input and security-related configuration coexist; no direct sensitive sink was demonstrated."
                finding["evidence"] = "Static lexical scan found input and security terminology, but no eval/exec/query/raw/shell:true sink."

    blockers = [item for item in findings if isinstance(item, dict) and item.get("severity") == "blocker"]
    majors = [item for item in findings if isinstance(item, dict) and item.get("severity") == "major"]
    normalized["verdict"] = "BLOCK" if blockers else "NEEDS WORK" if majors else "PASS"
    normalized["policy_adjustments"] = adjustments
    return normalized
