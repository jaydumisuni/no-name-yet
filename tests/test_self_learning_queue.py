from __future__ import annotations

import pytest

from main_review.self_learning_queue import (
    QueueContractError,
    add_case,
    attach_worker,
    council_complete,
    new_queue,
    transition,
)


def _candidate() -> dict:
    return {
        "case_id": "learn-a",
        "repository": "example/repo",
        "source_pr": 12,
        "defective_ref": "a" * 40,
        "fixing_ref": "b" * 40,
        "scored_paths": ["src/runtime.py"],
        "language": "python",
    }


def _worker(role: str, **extra) -> dict:
    base = {"role": role, "case_id": "learn-a", "confidence": 0.8}
    base.update(extra)
    return base


def test_queue_has_no_automatic_authority() -> None:
    queue = new_queue("week-1", authority_head="c" * 40, target_branch="train/week-1")
    assert queue["authority"] == {
        "may_auto_merge": False,
        "may_auto_promote": False,
        "final_verdict": "Sergeant",
    }


def test_queue_accepts_direct_event_lineage_without_source_pr() -> None:
    queue = new_queue("week-1", authority_head="c" * 40, target_branch="train/week-1")
    candidate = _candidate()
    candidate.pop("source_pr")
    candidate["source_event_url"] = "https://github.com/example/repo/commit/" + "b" * 40

    case = add_case(queue, candidate)

    assert case["source_event_url"].endswith("b" * 40)
    assert case["state"] == "collected"


def test_queue_requires_pr_or_direct_event_provenance() -> None:
    queue = new_queue("week-1", authority_head="c" * 40, target_branch="train/week-1")
    candidate = _candidate()
    candidate.pop("source_pr")

    with pytest.raises(QueueContractError, match="source_pr or source_event_url"):
        add_case(queue, candidate)


def test_truth_cannot_be_revealed_before_blind_freeze() -> None:
    queue = new_queue("week-1", authority_head="c" * 40, target_branch="train/week-1")
    add_case(queue, _candidate())
    with pytest.raises(QueueContractError, match="invalid transition"):
        transition(queue, "learn-a", "truth_revealed", artifact_name="truth_packet", artifact={"x": 1})


def test_three_isolated_workers_are_required() -> None:
    queue = new_queue("week-1", authority_head="c" * 40, target_branch="train/week-1")
    add_case(queue, _candidate())
    transition(queue, "learn-a", "blind_frozen", artifact_name="blind_result", artifact={"verdict": "APPROVE"})
    transition(queue, "learn-a", "truth_revealed", artifact_name="truth_packet", artifact={"fix": "diff"})
    attach_worker(queue, "learn-a", "teacher", _worker("teacher"))
    with pytest.raises(QueueContractError, match="all three"):
        council_complete(queue, "learn-a")


def test_defender_can_reject_a_lesson() -> None:
    queue = new_queue("week-1", authority_head="c" * 40, target_branch="train/week-1")
    add_case(queue, _candidate())
    transition(queue, "learn-a", "blind_frozen", artifact_name="blind_result", artifact={"verdict": "APPROVE"})
    transition(queue, "learn-a", "truth_revealed", artifact_name="truth_packet", artifact={"fix": "diff"})
    attach_worker(queue, "learn-a", "teacher", _worker("teacher"))
    attach_worker(queue, "learn-a", "prosecutor", _worker("prosecutor"))
    attach_worker(queue, "learn-a", "defender", _worker("defender", verdict="rejects"))
    result = council_complete(queue, "learn-a")
    assert result["state"] == "rejected"


def test_promotion_requires_controls_and_unrelated_transfer() -> None:
    queue = new_queue("week-1", authority_head="c" * 40, target_branch="train/week-1")
    add_case(queue, _candidate())
    transition(queue, "learn-a", "blind_frozen", artifact_name="blind_result", artifact={"verdict": "APPROVE"})
    transition(queue, "learn-a", "truth_revealed", artifact_name="truth_packet", artifact={"fix": "diff"})
    attach_worker(queue, "learn-a", "teacher", _worker("teacher"))
    attach_worker(queue, "learn-a", "prosecutor", _worker("prosecutor"))
    attach_worker(queue, "learn-a", "defender", _worker("defender", verdict="supports"))
    council_complete(queue, "learn-a")
    transition(queue, "learn-a", "controls_passed", artifact_name="negative_controls", artifact={"passed": True})
    transition(queue, "learn-a", "transfer_passed", artifact_name="transfer_result", artifact={"passed": True, "unrelated_language": True})
    result = transition(queue, "learn-a", "promotion_ready")
    assert result["decision"] == {
        "verdict": "promotion_candidate",
        "may_auto_merge": False,
        "may_auto_promote": False,
    }
