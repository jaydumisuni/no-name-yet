"""Final proof gate for Main Review.

This combines repository review and THETECHGUY verification evidence into a
single pass/fail gate. It is intentionally strict enough for CI while still
reporting exactly what evidence was used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .verdict import review_repository
from .verification import verify_repository_standard


def run_final_proof(root: str | Path = ".") -> dict[str, Any]:
    root_path = Path(root).resolve()
    review = review_repository(root_path)
    verification = verify_repository_standard(root_path).to_dict()

    review_verdict = review.get("verdict", {}) if isinstance(review, dict) else {}
    verdict_value = review_verdict.get("verdict") if isinstance(review_verdict, dict) else None
    verification_status = verification.get("status")

    passed = verdict_value == "PASS" and verification_status == "verified"
    blockers: list[str] = []

    if verdict_value != "PASS":
        blockers.append(f"Repository review did not PASS: {verdict_value}")
    if verification_status != "verified":
        blockers.append(f"Verification standard is not verified: {verification_status}")

    return {
        "passed": passed,
        "root": str(root_path),
        "blockers": blockers,
        "review_verdict": review_verdict,
        "verification": verification,
    }


def assert_final_proof(root: str | Path = ".") -> dict[str, Any]:
    result = run_final_proof(root)
    if not result["passed"]:
        blocker_text = "; ".join(result["blockers"])
        raise SystemExit(f"Final proof failed: {blocker_text}")
    return result
