#!/usr/bin/env python3
"""Export bounded learning proposals without raw fixing patches or credentials."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ALLOWED_STATES = {"council_complete", "controls_passed", "transfer_passed", "promotion_ready"}


def export(queue: dict[str, Any], output: Path) -> dict[str, Any]:
    root = output / str(queue["week_id"])
    root.mkdir(parents=True, exist_ok=True)
    proposals = []
    for case in queue.get("cases", []):
        if not isinstance(case, dict) or case.get("state") not in ALLOWED_STATES:
            continue
        workers = {
            role: packet.get("payload", {})
            for role, packet in case.get("workers", {}).items()
            if role in {"teacher", "prosecutor", "defender"} and isinstance(packet, dict)
        }
        proposal = {
            "schema_version": "sergeant.learning-proposal.v1",
            "week_id": queue["week_id"],
            "authority_head": queue["authority_head"],
            "case_id": case["case_id"],
            "repository": case["repository"],
            "source_pr": case["source_pr"],
            "language": case["language"],
            "defective_ref": case["defective_ref"],
            "fixing_ref": case["fixing_ref"],
            "scored_paths": case["scored_paths"],
            "state": case["state"],
            "blind_result_digest": case.get("artifacts", {}).get("blind_result", {}).get("digest"),
            "truth_packet_digest": case.get("artifacts", {}).get("truth_packet", {}).get("digest"),
            "workers": workers,
            "authority": {
                "may_auto_promote": False,
                "may_auto_merge": False,
                "requires_negative_controls": True,
                "requires_unrelated_language_transfer": True,
            },
        }
        destination = root / f"{case['case_id']}.json"
        destination.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        proposals.append(str(destination))
    index = {
        "schema_version": "sergeant.learning-proposal-index.v1",
        "week_id": queue["week_id"],
        "authority_head": queue["authority_head"],
        "proposal_count": len(proposals),
        "proposals": proposals,
        "automatic_promotions": 0,
        "automatic_merges": 0,
    }
    (root / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    index = export(queue, args.output)
    print(json.dumps(index, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
