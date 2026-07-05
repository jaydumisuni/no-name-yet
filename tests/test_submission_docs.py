from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_doc(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_submission_docs_capture_honest_claim_boundary() -> None:
    ready = read_doc("SUBMISSION_READY.md")
    brief = read_doc("docs/hackathon-submission.md")
    proof = read_doc("docs/submission-proof.md")

    combined = "\n".join([ready, brief, proof])

    assert "Secret detection" in combined
    assert "planted temp-file" in combined or "planted temporary-file" in combined
    assert "GitHub-shaped" in combined
    assert "Full live GitHub API ingestion" in combined
    assert "separate evidence step" in combined or "separate proof step" in combined


def test_submission_docs_keep_sergeant_as_reviewer_not_patch_writer() -> None:
    brief = read_doc("docs/hackathon-submission.md")
    proof = read_doc("docs/submission-proof.md")
    ready = read_doc("SUBMISSION_READY.md")

    combined = "\n".join([brief, proof, ready]).lower()

    assert "reviewer" in combined
    assert "automatic patch writer" in combined or "blind patch writer" in combined
    assert "pass" in combined
    assert "needs work" in combined
    assert "block" in combined


def test_roadmap_marks_live_ingestion_as_proof_gated() -> None:
    roadmap = read_doc("docs/08-roadmap.md")

    assert "Current status" in roadmap
    assert "Live GitHub read-only fetch" in roadmap
    assert "GitHub-shaped payload ingestion is verified" in roadmap
    assert "Full live API ingestion requires captured token/network evidence" in roadmap
    assert "full live GitHub API ingestion proof" in roadmap
