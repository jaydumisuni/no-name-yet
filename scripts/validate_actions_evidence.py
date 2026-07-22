#!/usr/bin/env python3
"""Validate a Sergeant Actions evidence preservation ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from main_review.actions_evidence import retained_bytes, validate_preservation_ledger


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.ledger.read_text(encoding="utf-8"))
    errors = validate_preservation_ledger(payload)
    summary = {
        "artifact_count": len(payload.get("records", [])),
        "retained_bytes": retained_bytes(payload.get("records", [])),
        "deletion_authorized": payload.get("deletion_authorized"),
        "workflow_run_deletion_authorized": payload.get("workflow_run_deletion_authorized"),
        "errors": errors,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
