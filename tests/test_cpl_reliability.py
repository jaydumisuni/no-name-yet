from __future__ import annotations

from pathlib import Path

import main_review.llm_review as llm_review_module
from main_review.cpl_experience import record_human_outcomes, retrieve_experience
from main_review.cpl_reliability import model_score, rank_models
from main_review.cpl_runtime import run_cpl_review
from main_review.llm_provider import LLMRoute, LLMSettings


def _outcome(finding_id: str, status: str, model: str, category: str = "correctness") -> dict:
    return {
        "finding_id": finding_id,
        "status": status,
        "category": category,
        "path": "src/app.py",
        "message": f"Outcome {finding_id}",
        "evidence_refs": [f"PROOF-{finding_id}"],
        "supporting_models": [model],
    }


def test_verified_service_records_rank_future_council_members() -> None:
    experience = {
        "profiles": {
            "model:model-a": {
                "missions_recorded": 2,
                "verified_outcomes": 0,
                "rejected_outcomes": 2,
                "observed_reliability": 0.0,
                "categories": ["correctness"],
            },
            "model:model-c": {
                "missions_recorded": 3,
                "verified_outcomes": 3,
                "rejected_outcomes": 0,
                "observed_reliability": 1.0,
                "categories": ["correctness"],
            },
        }
    }

    ranked = rank_models(["model-a", "model-b", "model-c"], experience, "correctness")

    assert ranked[0] == "model-c"
    assert ranked[-1] == "model-a"
    assert model_score("model-c", experience, "correctness") > model_score("model-b", experience, "correctness")


def test_automatic_cpl_primary_model_uses_verified_reliability(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def run():\n    return True\n", encoding="utf-8")
    record_human_outcomes(tmp_path, [
        _outcome("A-1", "rejected", "model-a"),
        _outcome("C-1", "verified", "model-c"),
        _outcome("C-2", "verified", "model-c"),
    ])
    monkeypatch.setenv("SERGEANT_CPL_DEPTH", "single")
    monkeypatch.setenv("SERGEANT_CPL_MAX_ROUNDS", "1")
    monkeypatch.setenv("SERGEANT_CPL_MAX_COUNCIL_MEMBERS", "3")
    monkeypatch.setattr(
        llm_review_module,
        "invoke_json",
        lambda *args, **kwargs: {
            "verdict": "PASS",
            "confidence": 0.9,
            "summary": "Grounded pass.",
            "findings": [],
            "unanswered_questions": [],
            "coverage": {"files_reviewed": ["src/app.py"], "areas": ["correctness"]},
        },
    )
    settings = LLMSettings(
        enabled=True,
        policy="preferred",
        provider="configured",
        base_url="http://127.0.0.1:9999/v1",
        model="",
        protocol="chat_completions",
        api_key="",
        timeout_seconds=1.0,
        max_output_tokens=1000,
    )
    route = LLMRoute(
        provider="test",
        base_url="http://127.0.0.1:9999/v1",
        model="model-a",
        protocol="chat_completions",
        discovered_models=("model-a", "model-b", "model-c"),
    )

    result = run_cpl_review(tmp_path, ["src/app.py"], {}, settings=settings, route=route)
    experience = retrieve_experience(tmp_path, ["src/app.py"], officers=["Engineer"])

    assert result["passes"][0]["model"] == "model-c"
    member = result["council"]["members"][0]
    assert member["model"] == "model-c"
    assert member["experience_profile"]["verified_outcomes"] == 2
    assert member["selection_score"] == model_score("model-c", experience)
