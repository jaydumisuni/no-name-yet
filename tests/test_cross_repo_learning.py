from __future__ import annotations

import json
from pathlib import Path

import pytest

from main_review.cross_repo_learning import (
    CrossRepositorySignalError,
    classify_signal,
    to_queue_candidate,
)
from main_review.self_learning_queue import QueueContractError, add_case, new_queue


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / ".github" / "self-learning" / "cross-repository-sources.json"
LUMI_TOKEN_ORIGIN_SIGNAL = (
    ROOT / ".github" / "self-learning" / "signals" / "lumi-token-origin-2026-07-23.json"
)
DOCTRINE = ROOT / "docs" / "51-cross-repository-learning-intake.md"
AGENTS = ROOT / "AGENTS.md"


def _ready_signal() -> dict:
    return {
        "repository": "jaydumisuni/lumi-dm",
        "event_kind": "repair",
        "source_url": "https://github.com/jaydumisuni/lumi-dm/commit/" + "b" * 40,
        "source_event_url": "https://github.com/jaydumisuni/lumi-dm/commit/" + "b" * 40,
        "defective_ref": "a" * 40,
        "fixing_ref": "b" * 40,
        "language": "javascript",
        "scored_paths": ["browser-extension/background-v5.js"],
        "evidence_refs": ["tests/test_browser_handoff.py", "workflow:runtime-proof"],
        "defect_confirmed": True,
        "fix_verified": True,
        "blind_review_possible": True,
        "concurrency_or_lifecycle": True,
    }


def test_formatting_commit_is_retained_as_evidence_not_promoted_to_lesson() -> None:
    result = classify_signal({
        "repository": "jaydumisuni/TechGuyCheckm8",
        "event_kind": "commit",
        "source_url": "https://github.com/jaydumisuni/TechGuyCheckm8/commit/064700fadc54b997b61d6d5d1c31ed13b844c673",
        "source_ref": "064700fadc54b997b61d6d5d1c31ed13b844c673",
        "summary": "Format Apple route reference crate",
        "language": "rust",
        "scored_paths": ["crates/tg-apple-route-reference/src/lib.rs"],
        "formatting_only": True,
        "behavior_change": False,
    })

    assert result["disposition"] == "evidence_only"
    assert result["candidate"] is None
    assert result["triage_private_count"] == 20
    assert result["authority"] == {
        "may_auto_promote": False,
        "may_auto_merge": False,
        "final_verdict": "Sergeant",
    }


def test_shell_trace_is_retained_until_defect_and_fix_lineage_are_recovered() -> None:
    result = classify_signal({
        "repository": "jaydumisuni/lumi-dm",
        "event_kind": "shell_trace",
        "source_url": "https://github.com/jaydumisuni/lumi-dm",
        "source_ref": "browser-extension/background-v5.js",
        "summary": "Located the active background worker and inspected the handoff implementation.",
        "scored_paths": ["browser-extension/background-v5.js"],
        "evidence_refs": ["shell:fd-and-rg-inspection"],
    })

    assert result["disposition"] == "needs_lineage"
    assert result["candidate"] is None
    assert result["triage_private_count"] == 20
    assert "defective/fixing lineage" in result["reason"]


def test_verified_direct_event_becomes_cross_repository_queue_candidate() -> None:
    signal = _ready_signal()
    result = classify_signal(signal)

    assert result["disposition"] == "candidate_ready"
    candidate = result["candidate"]
    assert candidate["repository"] == "jaydumisuni/lumi-dm"
    assert candidate["source_event_kind"] == "repair"
    assert candidate["cross_repository"] is True
    assert candidate["human_equivalent_workers"] == 3
    assert candidate["private_count"] == 30
    assert candidate["provenance_complete"] is True

    queue = new_queue("cross-repo-1", authority_head="c" * 40, target_branch="train/cross-repo")
    case = add_case(queue, candidate)
    assert case["state"] == "collected"
    assert case["source_event_url"].endswith("b" * 40)
    assert queue["authority"]["may_auto_promote"] is False
    assert queue["authority"]["may_auto_merge"] is False


def test_real_lumi_token_origin_miss_is_candidate_ready_but_unpromoted() -> None:
    signal = json.loads(LUMI_TOKEN_ORIGIN_SIGNAL.read_text(encoding="utf-8"))
    result = classify_signal(signal)

    assert result["disposition"] == "candidate_ready"
    assert result["human_equivalent_workers"] == 4
    assert result["triage_private_count"] == 40
    assert result["authority"] == {
        "may_auto_promote": False,
        "may_auto_merge": False,
        "final_verdict": "Sergeant",
    }

    candidate = result["candidate"]
    assert candidate["case_id"] == "learn-lumi-token-origin-20260723"
    assert candidate["defective_ref"] == "8f63f832112a2e0772e954c3e0319109ce21b6a9"
    assert candidate["fixing_ref"] == "a8d572258a4d53e9620970e5236ab21aa903580f"
    assert candidate["scored_paths"] == ["browser-extension/security-shim.js"]
    assert candidate["language"] == "javascript"
    assert candidate["private_count"] == 40
    assert signal["authority"]["may_auto_promote"] is False
    assert signal["authority"]["may_auto_merge"] is False

    queue = new_queue("week-1-lumi", authority_head="d" * 40, target_branch="train/cross-repo")
    case = add_case(queue, candidate)
    assert case["state"] == "collected"
    assert queue["authority"]["may_auto_promote"] is False
    assert queue["authority"]["may_auto_merge"] is False


def test_direct_candidate_conversion_fails_without_full_learning_boundary() -> None:
    signal = _ready_signal()
    signal["fix_verified"] = False

    with pytest.raises(CrossRepositorySignalError, match="verified defect/fix lineage"):
        to_queue_candidate(signal)


def test_queue_rejects_candidate_without_pr_or_source_event() -> None:
    queue = new_queue("cross-repo-1", authority_head="c" * 40, target_branch="train/cross-repo")
    candidate = {
        "case_id": "learn-missing-source",
        "repository": "example/repo",
        "defective_ref": "a" * 40,
        "fixing_ref": "b" * 40,
        "scored_paths": ["src/runtime.py"],
        "language": "python",
    }

    with pytest.raises(QueueContractError, match="source_pr or source_event_url"):
        add_case(queue, candidate)


def test_signal_rejects_repository_mismatch_and_credentials() -> None:
    signal = _ready_signal()
    signal["source_url"] = "https://github.com/other/repo/commit/" + "b" * 40
    with pytest.raises(CrossRepositorySignalError, match="declared GitHub repository"):
        classify_signal(signal)

    signal = _ready_signal()
    token_shaped_value = "gh" + "p_" + "a" * 22
    signal["summary"] = "authorization=" + token_shaped_value
    with pytest.raises(CrossRepositorySignalError, match="credential-like"):
        classify_signal(signal)


def test_source_registry_and_doctrine_keep_all_useful_repositories_eligible() -> None:
    registry = json.loads(SOURCES.read_text(encoding="utf-8"))
    repositories = {row["repository"] for row in registry["confirmed_sources"]}
    doctrine = DOCTRINE.read_text(encoding="utf-8")
    agents = AGENTS.read_text(encoding="utf-8")

    assert registry["policy"]["all_useful_repositories_may_contribute"] is True
    assert registry["policy"]["sergeant_repository_only"] is False
    assert registry["policy"]["automatic_promotions"] == 0
    assert registry["policy"]["automatic_merges"] == 0
    assert {"jaydumisuni/TechGuyCheckm8", "jaydumisuni/lumi-dm"} <= repositories
    assert "A signal does not need to originate in the Sergeant repository" in doctrine
    assert "Lumi token-origin benchmark" in doctrine
    assert "all useful THETECHGUY and external repository signals" in agents
    assert "not automatically a lesson" in agents
