from __future__ import annotations

from pathlib import Path

from main_review.llm_provider import LLMRoute, LLMSettings
from main_review.llm_review import run_llm_review


def _route(*, models: tuple[str, ...] = ("provider/glm-5.2",)) -> LLMRoute:
    return LLMRoute(
        provider="test",
        base_url="http://127.0.0.1:1/v1",
        model=models[0],
        protocol="chat_completions",
        timeout_seconds=1.0,
        max_output_tokens=2000,
        discovered_models=models,
    )


def _settings(policy: str = "preferred") -> LLMSettings:
    return LLMSettings(
        enabled=True,
        policy=policy,  # type: ignore[arg-type]
        provider="test",
        base_url="http://127.0.0.1:1/v1",
        model="provider/glm-5.2",
        protocol="chat_completions",
        api_key="",
        timeout_seconds=1.0,
        max_output_tokens=2000,
    )


def test_semantic_review_accepts_only_evidence_grounded_major_findings(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "def divide(total, count):\n    return total / count\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "main_review.llm_review.invoke_json",
        lambda route, **kwargs: {
            "verdict": "NEEDS WORK",
            "confidence": 0.92,
            "summary": "A zero divisor is not handled.",
            "findings": [
                {
                    "severity": "major",
                    "category": "correctness",
                    "path": "src/app.py",
                    "line_start": 2,
                    "line_end": 2,
                    "message": "The function can divide by zero.",
                    "evidence": "return total / count",
                    "why_it_matters": "A zero count raises ZeroDivisionError.",
                    "safer_alternative": "Validate count or define zero-count behavior.",
                }
            ],
            "unanswered_questions": [],
            "coverage": {"files_reviewed": ["src/app.py"], "areas": ["correctness"]},
        },
    )

    result = run_llm_review(
        tmp_path,
        ["src/app.py"],
        {"repository_review": {"verdict": "PASS"}},
        settings=_settings(),
        route=_route(),
    )

    assert result["status"] == "completed"
    assert result["verdict"] == "NEEDS WORK"
    assert result["findings"][0]["evidence_verified"] is True
    assert result["findings"][0]["path"] == "src/app.py"


def test_semantic_review_discards_hallucinated_major_finding(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('safe')\n", encoding="utf-8")

    monkeypatch.setattr(
        "main_review.llm_review.invoke_json",
        lambda route, **kwargs: {
            "verdict": "BLOCK",
            "confidence": 0.99,
            "summary": "Invented problem.",
            "findings": [
                {
                    "severity": "blocker",
                    "category": "security",
                    "path": "src/app.py",
                    "line_start": 1,
                    "line_end": 1,
                    "message": "Hard-coded production password.",
                    "evidence": "PASSWORD = 'production-secret'",
                    "why_it_matters": "Credential exposure.",
                    "safer_alternative": "Use a secret store.",
                }
            ],
            "coverage": {"files_reviewed": ["src/app.py"], "areas": ["security"]},
        },
    )

    result = run_llm_review(
        tmp_path,
        ["src/app.py"],
        {},
        settings=_settings(),
        route=_route(),
    )

    assert result["verdict"] == "PASS"
    assert result["findings"] == []
    assert result["passes"][0]["raw_verdict"] == "BLOCK"


def test_required_semantic_review_blocks_when_no_route_is_available(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main_review.llm_review.discover_route", lambda settings: None)

    result = run_llm_review(
        tmp_path,
        [],
        {},
        settings=_settings("required"),
    )

    assert result["status"] == "unavailable"
    assert result["verdict"] == "NEEDS WORK"
    assert result["policy"] == "required"


def test_adaptive_council_uses_a_second_open_model_for_high_risk_changes(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "review.yml").write_text(
        "permissions:\n  contents: read\n",
        encoding="utf-8",
    )
    calls: list[str] = []

    def fake_invoke(route, **kwargs):
        calls.append(route.model)
        return {
            "verdict": "PASS",
            "confidence": 0.85,
            "summary": f"Reviewed by {route.model}",
            "findings": [],
            "coverage": {
                "files_reviewed": [".github/workflows/review.yml"],
                "areas": ["automation"],
            },
        }

    monkeypatch.setattr("main_review.llm_review.invoke_json", fake_invoke)
    monkeypatch.setenv("SERGEANT_LLM_COUNCIL", "adaptive")

    result = run_llm_review(
        tmp_path,
        [".github/workflows/review.yml"],
        {"standard": {"passed": True}},
        settings=_settings(),
        route=_route(models=("provider/glm-5.2", "provider/qwen3-coder-next")),
    )

    assert calls == ["provider/glm-5.2", "provider/qwen3-coder-next"]
    assert len(result["passes"]) == 2
    assert result["verdict"] == "PASS"
