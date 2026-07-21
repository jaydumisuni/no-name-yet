#!/usr/bin/env python3
"""Run one bounded Sergeant self-learning round.

The blind result is frozen before the fixing diff is exposed to learning workers.
The round may produce lesson proposals, but it never promotes or merges them.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from main_review.adaptive_curriculum import plan_curriculum_round
from main_review.hermes_learning import LearningWorkerError, worker_request
from main_review.self_learning_queue import (
    add_case,
    attach_worker,
    council_complete,
    new_queue,
    transition,
    write_queue,
)

try:
    from scripts.run_static_training_set import run_manifest
except ImportError:  # Direct execution as python scripts/<name>.py.
    from run_static_training_set import run_manifest


def _run(*args: str, cwd: Path | None = None, capture: bool = False) -> str:
    completed = subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return completed.stdout if capture else ""


def _checkout(case: dict[str, Any], root: Path) -> Path:
    destination = root / case["case_id"]
    destination.mkdir(parents=True, exist_ok=False)
    _run("git", "init", str(destination))
    _run("git", "-C", str(destination), "remote", "add", "origin", f"https://github.com/{case['repository']}.git")
    _run("git", "-C", str(destination), "config", "core.sparseCheckout", "true")
    _run("git", "-C", str(destination), "config", "core.sparseCheckoutCone", "false")
    sparse = destination / ".git" / "info" / "sparse-checkout"
    sparse.parent.mkdir(parents=True, exist_ok=True)
    sparse.write_text("".join(f"/{path}\n" for path in case["scored_paths"]), encoding="utf-8")
    for ref in (case["fixing_ref"], case["defective_ref"]):
        _run("git", "-C", str(destination), "fetch", "--no-tags", "--filter=blob:none", "origin", ref)
    _run("git", "-C", str(destination), "merge-base", "--is-ancestor", case["defective_ref"], case["fixing_ref"])
    _run("git", "-C", str(destination), "checkout", "--detach", case["defective_ref"])
    actual = _run("git", "-C", str(destination), "rev-parse", "HEAD", capture=True).strip()
    if actual != case["defective_ref"]:
        raise RuntimeError(f"defective checkout mismatch for {case['case_id']}")
    for path in case["scored_paths"]:
        if not (destination / path).is_file():
            raise RuntimeError(f"scored path missing at defective ref: {path}")
    return destination


def _blind_manifest(case: dict[str, Any], checkout: Path, reviewer: str) -> dict[str, Any]:
    return {
        "schema_version": "sergeant.review-training.v1",
        "set_id": f"self-learning-{case['case_id']}",
        "purpose": "Controlled blind review before learning truth reveal.",
        "rules": {
            "models_enabled": False,
            "workspace_default": "none",
            "expected_defects_visible_to_sergeant": False,
            "classification": "untouched_transfer_validation",
            "provenance_required": True,
            "provenance_contract": "sergeant.training-provenance.v1",
            "reviewer_code_frozen_before_target_selection": reviewer,
        },
        "cases": [{
            "case_id": case["case_id"],
            "repository": case["repository"],
            "source_pr": case["source_pr"],
            "checkout_path": str(checkout),
            "defective_ref": case["defective_ref"],
            "fixing_ref": case["fixing_ref"],
            "changed_files": list(case["scored_paths"]),
            "workspace_policy": "static_first",
        }],
    }


def _truth_packet(case: dict[str, Any], checkout: Path, blind_result: dict[str, Any]) -> dict[str, Any]:
    command = [
        "git", "-C", str(checkout), "diff", "--no-ext-diff", "--unified=25",
        case["defective_ref"], case["fixing_ref"], "--", *case["scored_paths"],
    ]
    diff = subprocess.check_output(command, text=True, encoding="utf-8", errors="replace", timeout=300)
    if len(diff) > 24_000:
        diff = diff[:24_000] + "\n[TRUNCATED AFTER 24000 CHARACTERS]\n"
    summary = blind_result.get("summaries", [{}])[0]
    return {
        "case_id": case["case_id"],
        "repository": case["repository"],
        "language": case["language"],
        "source_pr": case["source_pr"],
        "defective_ref": case["defective_ref"],
        "fixing_ref": case["fixing_ref"],
        "scored_paths": case["scored_paths"],
        "blind_summary": summary,
        "fixing_diff": diff,
        "instruction_boundary": {
            "derive_general_mechanism": True,
            "copy_fix_identifiers_into_detector": False,
            "automatic_promotion": False,
        },
    }


def run_round(
    *, candidates_packet: dict[str, Any], history: dict[str, Any], output_dir: Path,
    authority_head: str, target_branch: str, count: int,
) -> dict[str, Any]:
    plan = plan_curriculum_round(
        candidates=candidates_packet.get("candidates", []),
        current_tier=int(history.get("current_tier", 0) or 0),
        recent_results=list(history.get("recent_results", [])),
        language_history=list(history.get("language_history", [])),
        count=count,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "curriculum-plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    queue = new_queue(candidates_packet["week_id"], authority_head=authority_head, target_branch=target_branch)
    checkout_root = output_dir / "checkouts"
    checkout_root.mkdir()

    for selected in plan["cases"]:
        case = {
            **selected,
            "scored_paths": list(selected["scored_paths"]),
        }
        add_case(queue, case)
        checkout = _checkout(case, checkout_root)
        manifest = _blind_manifest(case, checkout, authority_head)
        case_dir = output_dir / "cases" / case["case_id"]
        case_dir.mkdir(parents=True)
        manifest_path = case_dir / "blind-manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        blind_result = run_manifest(manifest_path, case_dir / "blind-result.json")
        transition(queue, case["case_id"], "blind_frozen", artifact_name="blind_result", artifact=blind_result)

        truth = _truth_packet(case, checkout, blind_result)
        (case_dir / "truth-packet.json").write_text(json.dumps(truth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        transition(queue, case["case_id"], "truth_revealed", artifact_name="truth_packet", artifact=truth)

        worker_errors: dict[str, str] = {}
        for role in ("teacher", "prosecutor", "defender"):
            try:
                packet = worker_request(role, truth)
                attach_worker(queue, case["case_id"], role, packet)
                (case_dir / f"{role}.json").write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            except LearningWorkerError as exc:
                worker_errors[role] = str(exc)
        if worker_errors:
            row = next(item for item in queue["cases"] if item["case_id"] == case["case_id"])
            row["worker_errors"] = worker_errors
            continue
        council_complete(queue, case["case_id"])
        proposal = next(item for item in queue["cases"] if item["case_id"] == case["case_id"])
        (case_dir / "lesson-proposal.json").write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    write_queue(queue, output_dir / "learning-queue.json")
    summary = {
        "schema_version": "sergeant.controlled-self-learning-result.v1",
        "week_id": candidates_packet["week_id"],
        "authority_head": authority_head,
        "target_branch": target_branch,
        "planned_cases": len(plan["cases"]),
        "candidate_shortfall": plan["candidate_shortfall"],
        "state_counts": {
            state: sum(1 for row in queue["cases"] if row.get("state") == state)
            for state in sorted({str(row.get("state")) for row in queue["cases"]})
        },
        "worker_error_cases": sum(1 for row in queue["cases"] if row.get("worker_errors")),
        "automatic_promotions": 0,
        "automatic_merges": 0,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--history", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--authority-head", required=True)
    parser.add_argument("--target-branch", required=True)
    parser.add_argument("--count", type=int, default=3)
    args = parser.parse_args()
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    history = json.loads(args.history.read_text(encoding="utf-8")) if args.history and args.history.exists() else {}
    summary = run_round(
        candidates_packet=candidates,
        history=history,
        output_dir=args.output_dir,
        authority_head=args.authority_head,
        target_branch=args.target_branch,
        count=max(1, min(3, args.count)),
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
