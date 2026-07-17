#!/usr/bin/env python3
"""Run Sergeant first against external defective revisions without model or runtime help.

The manifest contains only repository identity, exact defective revision, and review
scope. Expected defects are deliberately absent so Sergeant's report can be frozen
before the later fix is inspected.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from main_review.external_static_review import run_external_static_review


def _verdict_value(result: dict[str, Any]) -> str:
    verdict = result.get("verdict")
    if isinstance(verdict, dict):
        return str(verdict.get("verdict") or verdict.get("recommendation") or "UNKNOWN")
    return str(verdict or "UNKNOWN")


def _list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _summary(case: dict[str, Any], result: dict[str, Any], elapsed: float) -> dict[str, Any]:
    council = result.get("officer_council") if isinstance(result.get("officer_council"), dict) else {}
    cpl = result.get("cpl_review") if isinstance(result.get("cpl_review"), dict) else {}
    admitted = _list(council.get("admitted_findings"))
    advisory = _list(council.get("advisory_findings"))
    rejected = _list(council.get("rejected_findings"))
    assurances = _list(council.get("unresolved_assurances"))
    return {
        "case_id": case["case_id"],
        "repository": case["repository"],
        "defective_ref": case["defective_ref"],
        "source_pr": case["source_pr"],
        "workspace_policy": case.get("workspace_policy", "static_first"),
        "policy_profile": result.get("policy_profile", "external_static"),
        "review_mode": result.get("review_mode", "snapshot"),
        "verdict": _verdict_value(result),
        "admitted_finding_count": len(admitted),
        "advisory_finding_count": len(advisory),
        "rejected_finding_count": len(rejected),
        "unresolved_assurance_count": len(assurances),
        "model_status": cpl.get("status", "disabled"),
        "model_calls": int(cpl.get("model_call_count", 0) or 0),
        "elapsed_seconds": round(elapsed, 3),
        "unavailable_requested_files": list(result.get("unavailable_requested_files", [])),
        "admitted_roots": [
            {
                "root_cause": item.get("root_cause"),
                "severity": item.get("severity"),
                "path": item.get("path") or item.get("evidence_ref"),
                "message": item.get("message") or item.get("claim"),
            }
            for item in admitted
            if isinstance(item, dict)
        ],
    }


def run_manifest(manifest_path: Path, output_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("training manifest must contain at least one case")

    # This development lane measures the permanent model-free formation.
    os.environ["SERGEANT_LLM_ENABLED"] = "false"
    os.environ["SERGEANT_CPL_ENABLED"] = "false"
    os.environ["SERGEANT_CPL_POLICY"] = "disabled"

    full_results: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for raw_case in cases:
        if not isinstance(raw_case, dict):
            raise ValueError("every training case must be an object")
        case = dict(raw_case)
        root = Path(case["checkout_path"]).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"case checkout is missing: {root}")
        requested_files = [str(item) for item in case.get("changed_files", []) if str(item)]
        if not requested_files:
            raise ValueError(f"case {case.get('case_id')} has no review scope")

        started = time.monotonic()
        result = run_external_static_review(root, requested_files, review_mode="snapshot")
        elapsed = time.monotonic() - started
        full_results.append({"case": case, "result": result})
        summaries.append(_summary(case, result, elapsed))

    payload = {
        "schema_version": "sergeant.static-training-result.v2",
        "set_id": manifest.get("set_id"),
        "rules": manifest.get("rules", {}),
        "case_count": len(summaries),
        "summaries": summaries,
        "full_results": full_results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = run_manifest(args.manifest, args.output)
    print(json.dumps({"set_id": payload["set_id"], "summaries": payload["summaries"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
