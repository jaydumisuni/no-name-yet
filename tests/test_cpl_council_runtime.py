from __future__ import annotations

from pathlib import Path

import main_review.cpl_runtime as cpl_runtime_module
import main_review.llm_review as llm_review_module
from main_review.cpl_council import assess, gap_signature, instruction
from main_review.cpl_experience import detect_recurrences, record_human_outcomes, retrieve_experience
from main_review.cpl_runtime import run_cpl_review
from main_review.learning_loop import run_learning_loop
from main_review.llm_provider import LLMRoute, LLMSettings
from main_review.memory import ReviewMemoryStore, default_memory_path, new_memory_record
from main_review.squad import run_squad_review


def _payload(*, verdict: str = "PASS", confidence: float = 0.9, findings: list[dict] | None = None) -> dict:
    return {
        "verdict": verdict,
        "confidence": confidence,
        "summary": f"{verdict} report",
        "findings": findings or [],
        "unanswered_questions": [],
        "coverage": {"files_reviewed": ["src/app.py"], "areas": ["correctness"]},
    }


def _major_finding() -> dict:
    return {
        "severity": "major",
        "category": "correctness",
        "path": "src/app.py",
        "line_start": 2,
        "line_end": 2,
        "message": "The function returns the failure state unconditionally.",
        "evidence": "return False",
        "why_it_matters": "The caller can never observe success.",
        "safer_alternative": "Return the computed result and prove both branches.",
    }


def _settings() -> LLMSettings:
    return LLMSettings(
        enabled=True,
        policy="preferred",
        provider="configured",
        base_url="http://127.0.0.1:9999/v1",
        model="model-a",
        protocol="chat_completions",
        api_key="",
        timeout_seconds=1.0,
        max_output_tokens=1000,
    )


def _route() -> LLMRoute:
    return LLMRoute(
        provider="test",
        base_url="http://127.0.0.1:9999/v1",
        model="model-a",
        protocol="chat_completions",
        discovered_models=("model-a", "model-b", "model-c", "model-d"),
    )


def test_cpl_runs_repeated_multi_model_council_until_named_gaps_are_answered(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def run():\n    return False\n", encoding="utf-8")
    monkeypatch.setenv("SERGEANT_CPL_DEPTH", "deep")
    monkeypatch.setenv("SERGEANT_CPL_MAX_PASSES", "2")
    monkeypatch.setenv("SERGEANT_CPL_MAX_ROUNDS", "3")
    monkeypatch.setenv("SERGEANT_CPL_MAX_COUNCIL_MEMBERS", "4")

    first_round = iter([
        _payload(),
        _payload(verdict="NEEDS WORK", findings=[_major_finding()]),
    ])
    later_rounds = iter([
        _payload(),
        _payload(verdict="NEEDS WORK", findings=[_major_finding()]),
    ])
    monkeypatch.setattr(llm_review_module, "invoke_json", lambda *args, **kwargs: next(first_round))
    monkeypatch.setattr(cpl_runtime_module, "invoke_json", lambda *args, **kwargs: next(later_rounds))

    result = run_cpl_review(
        tmp_path,
        ["src/app.py"],
        {"repository_review": {"verdict": "PASS"}},
        settings=_settings(),
        route=_route(),
    )

    assert result["verdict"] == "NEEDS WORK"
    assert result["memory_checked"] is True
    assert len(result["passes"]) == 4
    assert result["council"]["round_count"] == 3
    assert result["council"]["member_count"] == 4
    assert result["council"]["true_model_independence"] is True
    assert result["council"]["complete"] is True
    assert result["council"]["final_gaps"] == []
    assert [item["admission"] for item in result["council"]["recruitment"]] == ["new_member", "new_member"]
    assert result["passes"][2]["resolution_status"] == "answered"
    assert result["passes"][3]["resolution_status"] == "answered"
    assert result["passes"][3]["supported_officer"] == "Engineer"


def test_answered_council_gap_does_not_reappear() -> None:
    gap = {"type": "disagreement", "specialist": "tests_contracts", "officer": "Engineer", "reason": "Council verdicts disagree: NEEDS WORK, PASS."}
    command = instruction(gap, 2)
    passes = [
        {"specialist": "generalist", "verdict": "PASS", "findings": [], "unanswered_questions": []},
        {"specialist": "correctness", "verdict": "NEEDS WORK", "findings": [], "unanswered_questions": []},
        {
            "specialist": "tests_contracts",
            "verdict": "PASS",
            "findings": [],
            "unanswered_questions": [],
            "resolved_gap_signature": command["gap_signature"],
            "resolution_status": "answered",
        },
    ]

    gaps = assess(passes, [], [], 3)

    assert gap_signature(gap) not in {gap_signature(item) for item in gaps}


def test_verified_outcomes_feed_cpl_officer_model_memory_and_recurrence(tmp_path: Path) -> None:
    store = ReviewMemoryStore(default_memory_path(tmp_path))
    store.add(new_memory_record(
        kind="risk",
        title="Return-state regression",
        summary="Verify both return branches.",
        reason="A previous repair returned failure unconditionally.",
        status="verified",
        applies_to=["src/app.py"],
        evidence=["TEST-1"],
        confidence=0.9,
    ))
    outcome = {
        "finding_id": "F-1",
        "status": "verified",
        "category": "correctness",
        "path": "src/app.py",
        "message": "The function returns the failure state unconditionally.",
        "evidence_refs": ["TEST-1"],
        "supporting_models": ["model-a"],
        "weapons": ["regression-tests"],
    }

    added = record_human_outcomes(tmp_path, [outcome])
    duplicate = record_human_outcomes(tmp_path, [outcome])
    experience = retrieve_experience(tmp_path, ["src/app.py"], officers=["Engineer"])
    recurrences = detect_recurrences([_major_finding()], experience)

    assert len(added) == 4
    assert duplicate == []
    assert experience["events"]
    assert experience["canonical_lessons"][0]["lesson"] == "Verify both return branches."
    assert experience["profiles"]["officer:Engineer"]["verified_outcomes"] == 1
    assert experience["profiles"]["model:model-a"]["verified_outcomes"] == 1
    assert recurrences[0]["previous_event_id"]


def test_learning_loop_writes_canonical_and_operational_experience(tmp_path: Path) -> None:
    review_result = {
        "ranked_findings": [{
            "message": "Known return-state defect",
            "category": "correctness",
            "path": "src/app.py",
            "evidence": "return False",
            "supporting_models": ["model-a"],
            "weapons": ["regression-tests"],
            "confidence": 0.9,
        }]
    }

    result = run_learning_loop(
        tmp_path,
        review_result,
        [{"finding_index": "0", "decision": "accepted", "reason": "Runtime proof confirmed it."}],
        write=True,
    )

    assert result["written"]["written_count"] == 1
    assert result["written"]["experience_event_count"] == 4
    assert default_memory_path(tmp_path).is_file()
    assert (tmp_path / ".main-review" / "cpl-experience.jsonl").is_file()


def test_squad_delivers_officer_experience_council_orders_and_recruited_bots() -> None:
    cpl = {
        "status": "completed",
        "verdict": "PASS",
        "confidence": 0.9,
        "memory_checked": True,
        "experience": {
            "events": [{"subject_type": "officer", "subject_id": "Engineer", "status": "verified", "message": "Known contract pattern"}],
            "profiles": {"officer:Engineer": {"observed_reliability": 1.0}},
            "anti_repeat_rule": "Use applicable experience.",
        },
        "reasoning_plan": [],
        "passes": [
            {"specialist": "generalist", "model": "model-a", "provider": "test", "verdict": "PASS", "confidence": 0.9, "findings": []},
            {
                "specialist": "architecture",
                "specialist_title": "Architecture Support Bot",
                "supported_officer": "Engineer",
                "model": "model-b",
                "provider": "test",
                "verdict": "PASS",
                "confidence": 0.9,
                "council_round": 2,
                "council_member_role": "recruited_gap_specialist",
                "admission": "new_member",
                "findings": [],
            },
        ],
        "council": {
            "mode": "elastic_multi_model",
            "round_count": 2,
            "member_count": 2,
            "agreement": 1.0,
            "model_independence": 1.0,
            "complete": True,
            "final_gaps": [],
            "officer_instructions": [{"to_officer": "Engineer", "instruction": "Recheck the contract."}],
        },
        "recurrences": [],
    }
    packet = {
        "repository_review": {"findings": []},
        "capability_review": {"findings": []},
        "review_intelligence": {"ranked_findings": []},
        "cpl_review": cpl,
    }

    result = run_squad_review(packet, {"classified_findings": []}, {}, {"verdict": "TRUSTED_WITH_WATCH"})
    engineer = next(item for item in result["reports"] if item["agent"] == "engineer")

    assert any(item["kind"] == "officer_experience" for item in engineer["cpl_support"])
    assert any(item["kind"] == "officer_support_bot" and item["council_round"] == 2 for item in engineer["cpl_support"])
    assert result["cpl_command"]["council"]["member_count"] == 2
    assert result["cpl_command"]["memory_checked"] is True
