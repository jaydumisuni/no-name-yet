#!/usr/bin/env python3
"""Opaque transfer selector v8 with capability-addition rejection.

Selector v8 reuses the proven v7 production-source, test-change, ancestry,
prior-repository and bidirectional executable-change gates. It adds two truth
boundaries: capability additions require evidence of a pre-existing behavioral
contract violation, and canonical Perl ``.t`` files count as changed tests
without relaxing any production-source or executable-change requirement.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from . import select_opaque_transfer_candidates as base
except ImportError:  # Direct CLI execution from scripts/.
    import select_opaque_transfer_candidates as base

_BASE_QUALIFIES = base._qualifies

_CAPABILITY_TITLE_RE = re.compile(
    r"^\s*(?:feat(?:ure)?|add|introduce|implement|enable|allow|support|expose|provide)"
    r"(?:\b|\s*[:(])",
    re.I,
)
_CAPABILITY_PHRASES = (
    "add support for", "adds support for", "adding support for",
    "support for a new", "support a new", "new feature", "feature request",
    "enable support", "enables support", "allow users to", "allows users to",
    "introduce support", "introduces support", "implement support",
    "implements support", "not currently supported", "previously unsupported",
    "newly supported", "expose a new", "provide a new",
)
_PREEXISTING_DEFECT_RE = re.compile(
    r"\b(?:bug|regression|crash|panic|incorrect|wrong|broken|not working|does not work|"
    r"fails?|failure|error|exception|race|deadlock|hang|leak|data loss|corrupt(?:ion|ed)?|"
    r"stale|duplicate|timeout|underflow|overflow|security|vulnerab\w*|invalid result|"
    r"unexpected result|misbehav\w*|silently drops?|loses? data|cannot recover|"
    r"wrong order|out of order)\b",
    re.I,
)


def _looks_like_capability_addition(title: str, body: str) -> bool:
    combined = f"{title}\n{body}".lower()
    return bool(_CAPABILITY_TITLE_RE.search(title)) or any(
        phrase in combined for phrase in _CAPABILITY_PHRASES
    )


def _has_preexisting_defect_evidence(title: str, body: str) -> bool:
    return bool(_PREEXISTING_DEFECT_RE.search(f"{title}\n{body}"))


def _rows_with_perl_test_aliases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expose canonical Perl .t changes to the proven v7 test-change gate.

    The alias exists only in memory during qualification. Production paths,
    patches and the persisted opaque packet remain unchanged.
    """

    normalized: list[dict[str, Any]] = []
    for row in rows:
        filename = str(row.get("filename") or "")
        if Path(filename.replace("\\", "/")).suffix.lower() != ".t":
            normalized.append(row)
            continue
        if base._is_test_file(filename):
            normalized.append(row)
            continue
        alias = dict(row)
        alias["filename"] = f"tests/{Path(filename).name}"
        normalized.append(alias)
    return normalized


def _qualifies_v8(pr: dict[str, Any], rows: list[dict[str, Any]], source_files: list[str]) -> bool:
    normalized_rows = _rows_with_perl_test_aliases(rows)
    if not _BASE_QUALIFIES(pr, normalized_rows, source_files):
        return False
    title = str(pr.get("title") or "")
    body = str(pr.get("body") or "")
    if _looks_like_capability_addition(title, body) and not _has_preexisting_defect_evidence(title, body):
        return False
    return True


def select(*, reviewer: str, set_id: str, lanes: list[dict[str, Any]], output: Path) -> None:
    original = base._qualifies
    base._qualifies = _qualifies_v8
    try:
        base.select(reviewer=reviewer, set_id=set_id, lanes=lanes, output=output)
    finally:
        base._qualifies = original

    packet = json.loads(output.read_text(encoding="utf-8"))
    packet["schema_version"] = "sergeant.opaque-candidate-selection.v8"
    packet["capability_addition_exclusion"] = True
    packet["preexisting_behavioral_contract_evidence_required"] = True
    packet["feature_enablement_without_defect_rejected"] = True
    packet["canonical_perl_t_tests_recognized"] = True
    output.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--set-id", required=True)
    parser.add_argument("--lanes-json", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    lanes = json.loads(Path(args.lanes_json).read_text(encoding="utf-8"))
    if not isinstance(lanes, list) or len(lanes) != 3:
        raise SystemExit("lanes JSON must contain exactly three lanes")
    select(reviewer=args.reviewer, set_id=args.set_id, lanes=lanes, output=Path(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
