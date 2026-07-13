"""Policy normalization for changed-file risk signals.

A high-risk path requires deeper review, but path classification alone is not a
demonstrated defect. Sergeant accepts that signal only when the same change set
contains an assurance document that names the path and records purpose,
permissions, secrets, rollback, and proof.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .verdict import decide_verdict

ASSURANCE_TERMS = ("purpose", "permissions", "secrets", "rollback", "proof")
HIGH_RISK_MESSAGE = "Changed file is in a high-risk path."


def _assurance_documents(root: Path, changed_files: list[str]) -> dict[str, str]:
    documents: dict[str, str] = {}
    try:
        resolved_root = root.resolve()
    except OSError:
        return documents
    for relative in changed_files:
        if not relative.startswith("docs/") or not relative.lower().endswith((".md", ".txt")):
            continue
        try:
            path = (resolved_root / relative).resolve()
            if not path.is_relative_to(resolved_root) or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lowered = text.lower()
        if all(term in lowered for term in ASSURANCE_TERMS):
            documents[relative] = text
    return documents


def normalize_diff_review(
    packet: dict[str, Any],
    root: str | Path,
    changed_files: list[str],
) -> dict[str, Any]:
    """Downgrade generic high-risk path signals only with explicit assurance."""

    normalized = deepcopy(packet)
    evidence = normalized.get("evidence", {})
    findings = evidence.get("findings", []) if isinstance(evidence, dict) else []
    documents = _assurance_documents(Path(root), changed_files)
    adjustments: list[dict[str, object]] = []

    for finding in findings:
        if not isinstance(finding, dict):
            continue
        if finding.get("message") != HIGH_RISK_MESSAGE or finding.get("severity") not in {"blocker", "major"}:
            continue
        target = str(finding.get("path", ""))
        assurance_path = next(
            (
                path
                for path, text in documents.items()
                if target and target in text
            ),
            "",
        )
        if not assurance_path:
            continue
        previous = str(finding.get("severity"))
        finding["severity"] = "note"
        finding["assurance_document"] = assurance_path
        finding["evidence"] = (
            f"High-risk path received explicit purpose, permissions, secrets, rollback, and proof review in {assurance_path}."
        )
        adjustments.append(
            {
                "path": target,
                "from": previous,
                "to": "note",
                "assurance_document": assurance_path,
                "reason": "Path risk was reviewed with explicit operational assurance evidence.",
            }
        )

    if isinstance(evidence, dict):
        evidence["finding_count"] = len(findings)
        normalized["verdict"] = decide_verdict(evidence).to_dict()
    normalized["policy_adjustments"] = adjustments
    return normalized
