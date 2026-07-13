from __future__ import annotations

from pathlib import Path

import main_review.llm_review as llm_review_module
from main_review.cpl_runtime import run_cpl_review
from main_review.llm_provider import LLMRoute, LLMSettings


def test_unresolved_council_gap_prevents_a_pass_verdict(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def run():\n    return True\n", encoding="utf-8")
    monkeypatch.setenv("SERGEANT_CPL_DEPTH", "single")
    monkeypatch.setenv("SERGEANT_CPL_MAX_ROUNDS", "1")
    monkeypatch.setattr(
        llm_review_module,
        "invoke_json",
        lambda *args, **kwargs: {
            "verdict": "PASS",
            "confidence": 0.8,
            "summary": "The supplied excerpt looks safe, but a required proof is absent.",
            "findings": [],
            "unanswered_questions": ["Runtime proof for the changed branch is missing."],
            "coverage": {"files_reviewed": ["src/app.py"], "areas": ["correctness"]},
        },
    )
    settings = LLMSettings(
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
    route = LLMRoute(
        provider="test",
        base_url="http://127.0.0.1:9999/v1",
        model="model-a",
        protocol="chat_completions",
        discovered_models=("model-a",),
    )

    result = run_cpl_review(tmp_path, ["src/app.py"], {}, settings=settings, route=route)

    assert result["findings"] == []
    assert result["verdict"] == "NEEDS WORK"
    assert result["council"]["complete"] is False
    assert result["council"]["final_gaps"][0]["type"] == "unanswered_question"
    assert result["unanswered_questions"] == ["Runtime proof for the changed branch is missing."]
    assert "1 council gap(s) are unresolved" in result["summary"]
