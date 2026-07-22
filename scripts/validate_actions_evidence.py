#!/usr/bin/env python3
"""Validate Sergeant Actions preservation and optional recovery-replay evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

from main_review.actions_evidence import (
    retained_bytes,
    validate_preservation_ledger,
    validate_recovery_replay,
)


def _read_json(path: Path, label: str) -> tuple[object, list[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except OSError as error:
        return None, [f"unable to read {label}: {error}"]
    except json.JSONDecodeError as error:
        return None, [
            f"invalid {label} JSON: {error.msg} at line {error.lineno} column {error.colno}"
        ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()

    ledger, errors = _read_json(args.ledger, "ledger")
    replay: object = None
    if not errors:
        errors = validate_preservation_ledger(ledger)

    if args.replay is not None:
        replay, replay_errors = _read_json(args.replay, "replay")
        errors.extend(replay_errors)
        if not replay_errors and isinstance(ledger, Mapping) and isinstance(replay, Mapping):
            errors = validate_recovery_replay(ledger, replay)
        elif not replay_errors:
            errors.append("ledger and replay roots must be objects")

    ledger_mapping = ledger if isinstance(ledger, Mapping) else {}
    replay_mapping = replay if isinstance(replay, Mapping) else {}
    records = ledger_mapping.get("records", [])
    summary = {
        "artifact_count": len(records) if isinstance(records, list) else 0,
        "retained_bytes": retained_bytes(records) if isinstance(records, list) else 0,
        "recovery_replay_verified": bool(
            replay_mapping
            and replay_mapping.get("artifact_count") == replay_mapping.get("verified_count")
            and replay_mapping.get("failed_count") == 0
            and not errors
        ),
        "deletion_authorized": ledger_mapping.get("deletion_authorized"),
        "workflow_run_deletion_authorized": ledger_mapping.get("workflow_run_deletion_authorized"),
        "errors": errors,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
