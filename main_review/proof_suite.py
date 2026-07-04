"""End-to-end proof suite for Main Review.

This module exercises the review pipeline with deterministic fixtures so proof
continues even when an external reviewer such as CodeRabbit is unavailable or
rate-limited.
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .diff_review import review_changed_files
from .final_proof import run_final_proof
from .review_batch import batch_summary, run_review_learning_batch
from .verdict import review_repository
from .verification import verify_repository_standard


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_end_to_end_proof(root: str | Path = ".") -> dict[str, Any]:
    """Run all local proof phases and return one combined report."""
    root_path = Path(root).resolve()
    final_proof = run_final_proof(root_path)
    repository_review = review_repository(root_path)
    verification = verify_repository_standard(root_path).to_dict()
    diff_review = review_changed_files(
        [
            "main_review/final_proof.py",
            "tests/test_final_proof.py",
            ".github/workflows/ci.yml",
        ]
    )

    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        comments_file = temp_path / "external-comments.json"
        _write_json(
            comments_file,
            [
                {
                    "body": "Missing receiver validation test should be preserved as a reusable review lesson.",
                    "user": {"login": "coderabbitai"},
                    "path": "src/api.py",
                    "line": 12,
                    "classification": "🟢",
                    "reason": "Contract changes need receiver-side proof, not sender-only proof.",
                },
                {
                    "body": "Use a different variable naming style without project evidence.",
                    "user": {"login": "coderabbitai"},
                    "classification": "🔴",
                    "reason": "Style-only feedback is rejected unless it supports readability, consistency, or defects.",
                },
                {
                    "body": "Save pattern: untrusted review bots should not execute repository code without a sandbox.",
                    "user": {"login": "qodo-bot"},
                    "classification": "🧠",
                    "reason": "Static-first review protects repositories from reviewer supply-chain risk.",
                    "tags": ["security", "static-review"],
                },
            ],
        )
        review_batch = run_review_learning_batch(
            comments_file,
            root=temp_path,
            repository="jaydumisuni/no-name-yet",
            pr_number=0,
            write_memory=True,
        )
        review_batch_compact = batch_summary(review_batch)

    phases = {
        "final_proof": final_proof.get("passed") is True,
        "repository_review": repository_review.get("verdict", {}).get("verdict") == "PASS",
        "verification": verification.get("status") == "verified",
        "diff_review_runs": diff_review.get("verdict", {}).get("verdict") in {"PASS", "NEEDS WORK", "BLOCK"},
        "external_review_batch_runs": review_batch_compact.get("collected_comments") == 3,
        "external_review_memory_write_runs": review_batch_compact.get("memory_written") == 2,
    }

    return {
        "passed": all(phases.values()),
        "phases": phases,
        "final_proof": final_proof,
        "repository_review_verdict": repository_review.get("verdict", {}),
        "verification": verification,
        "diff_review_verdict": diff_review.get("verdict", {}),
        "review_batch_summary": review_batch_compact,
    }


def assert_end_to_end_proof(root: str | Path = ".") -> dict[str, Any]:
    result = run_end_to_end_proof(root)
    if not result["passed"]:
        failed = [name for name, passed in result["phases"].items() if not passed]
        raise SystemExit(f"End-to-end proof failed: {', '.join(failed)}")
    return result
