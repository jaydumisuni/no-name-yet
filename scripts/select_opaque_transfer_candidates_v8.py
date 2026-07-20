#!/usr/bin/env python3
"""Opaque transfer selector v8 with capability-addition rejection.

Selector v8 reuses the proven v7 production-source, test-change, ancestry,
prior-repository and bidirectional executable-change gates. It adds one new
truth boundary: adding support or enabling a new capability is not a defect
unless the candidate also contains concrete language describing a pre-existing
behavioral contract violation.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import select_opaque_transfer_candidates as base

_BASE_QUALIFIES = base._qualifies

_CAPABILITY_TITLE_RE = re.compile(
    r"^\s*(?:feat(?:ure)?|add|introduce|implement|enable|allow|support|expose|provide)"
    r"(?:\b|\s*[:(])",
    re.I,
)
_CAPABILITY_PHRASES = (
    "add support for",
    "adds support for",
    "adding support for",
    "support for a new",
    "support a new",
    "new feature",
    "feature request",
    "enable support",
    "enables support",
    "allow users to",
    "allows users to",
    "introduce support",
    "introduces support",
    "implement support",
    "implements support",
    "not currently supported",
    "previously unsupported",
    "newly supported",
    "expose a new",
    "provide a new",
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


def _qualifies_v8(
    pr: dict[str, Any],
    rows: list[dict[str, Any]],
    source_files: list[str],
) -> bool:
    if not _BASE_QUALIFIES(pr, rows, source_files):
        return False
    title = str(pr.get("title") or "")
    body = str(pr.get("body") or "")
    if _looks_like_capability_addition(title, body) and not _has_preexisting_defect_evidence(title, body):
        return False
    return True


def select(
    *,
    reviewer: str,
    set_id: str,
    lanes: list[dict[str, Any]],
    output: Path,
) -> None:
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
    select(
        reviewer=args.reviewer,
        set_id=args.set_id,
        lanes=lanes,
        output=Path(args.output),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
