#!/usr/bin/env python3
"""Classify one sanitized repository event for governed Sergeant learning."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from main_review.cross_repo_learning import classify_signal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("signal input must be a JSON object")
    result = classify_signal(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "repository": result["repository"],
        "disposition": result["disposition"],
        "triage_private_count": result["triage_private_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
