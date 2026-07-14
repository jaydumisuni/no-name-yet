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


def test_public_docs_exclude_private_roadmap_and_document_only_implemented_service() -> None:
    standalone = read_doc("docs/37-standalone-service.md")
    lowered = standalone.lower()

    assert not (ROOT / "docs/08-roadmap.md").exists()
    assert standalone.startswith("# Standalone Self-Hosted Service")
    assert "Implemented and proven as a public Sergeant deployment surface." in standalone
    assert "dependency-free standalone service" in standalone
    assert "repository writes" in standalone
    assert "does not automatically fetch code" in standalone
    assert "not implemented by this service" in standalone
    assert "private memory-system roadmaps do not belong in the open-source repository" in lowered
    assert "phase 8a" not in lowered
    assert "phase 8b" not in lowered
    assert "next active phase" not in lowered
