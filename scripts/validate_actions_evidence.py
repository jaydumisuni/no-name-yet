#!/usr/bin/env python3
"""Validate Sergeant Actions preservation and optional recovery-replay evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from main_review.actions_evidence import (
    retained_bytes,
    validate_preservation_ledger,
    validate_recovery_replay,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()

    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    replay = None
    errors = validate_preservation_ledger(ledger)
    if args.replay is not None:
        replay = json.loads(args.replay.read_text(encoding="utf-8"))
        errors = validate_recovery_replay(ledger, replay)

    summary = {
        "artifact_count": len(ledger.get("records", [])),
        "retained_bytes": retained_bytes(ledger.get("records", [])),
        "recovery_replay_verified": bool(
            replay is not None
            and replay.get("artifact_count") == replay.get("verified_count")
            and replay.get("failed_count") == 0
            and not errors
        ),
        "deletion_authorized": ledger.get("deletion_authorized"),
        "workflow_run_deletion_authorized": ledger.get("workflow_run_deletion_authorized"),
        "errors": errors,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
