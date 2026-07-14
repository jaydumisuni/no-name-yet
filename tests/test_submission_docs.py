from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_doc(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_submission_docs_capture_current_proven_claim_boundary() -> None:
    ready = read_doc("SUBMISSION_READY.md")
    brief = read_doc("docs/hackathon-submission.md")
    proof = read_doc("docs/submission-proof.md")

    combined = "\n".join([ready, brief, proof])

    assert "Secret detection" in combined
    assert "planted temporary-file" in combined or "planted temp-file" in combined
    assert "GitHub-shaped" in combined
    assert "Full live GitHub API ingestion" in combined
    assert "real read-only" in combined or "real GitHub API" in combined
    assert "no comment bodies" in combined or "omits comment bodies" in combined
    assert "write-side GitHub App" in combined or "writes GitHub reviews" in combined


def test_submission_docs_keep_sergeant_as_reviewer_not_patch_writer() -> None:
    brief = read_doc("docs/hackathon-submission.md")
    proof = read_doc("docs/submission-proof.md")
    ready = read_doc("SUBMISSION_READY.md")

    combined = "\n".join([brief, proof, ready]).lower()

    assert "reviewer" in combined
    assert "blind patch writer" in combined or "automatic patching" in combined or "applies patches" in combined
    assert "pass" in combined
    assert "needs work" in combined
    assert "block" in combined
    assert "does not execute" in combined or "executes pull-request-controlled code" in combined


def test_roadmap_marks_phase_7_complete_and_phase_8_next() -> None:
    roadmap = read_doc("docs/08-roadmap.md")

    assert "Current status" in roadmap
    assert "Live GitHub read-only fetch" in roadmap
    assert "Full live GitHub API ingestion is proven" in roadmap
    assert "## Phase 7 — Production hardening" in roadmap
    assert "Status: complete for the current public reviewer boundary." in roadmap
    assert "## Phase 8 — Standalone product path" in roadmap
    assert "Status: next major product phase." in roadmap
