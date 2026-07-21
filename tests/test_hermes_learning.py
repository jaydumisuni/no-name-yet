from __future__ import annotations

import json

import pytest

from main_review.hermes_learning import (
    LearningWorkerError,
    WorkerConfig,
    validate_worker_output,
    worker_request,
)


def test_teacher_contract_requires_generalized_controls() -> None:
    packet = {
        "role": "teacher",
        "case_id": "case-a",
        "generalized_mechanism": "resource claim happens after an await",
        "proposed_detector": "track claim ordering across suspension points",
        "positive_tests": ["claim after await"],
        "negative_controls": ["claim before await with rollback"],
        "transfer_languages": ["rust", "java"],
        "confidence": 0.8,
    }
    assert validate_worker_output("teacher", "case-a", packet)["proposed_detector"]


def test_role_and_case_binding_are_strict() -> None:
    with pytest.raises(LearningWorkerError, match="role mismatch"):
        validate_worker_output(
            "teacher",
            "case-a",
            {
                "role": "defender",
                "case_id": "case-a",
                "confidence": 0.5,
            },
        )


def test_defender_verdict_is_bounded() -> None:
    with pytest.raises(LearningWorkerError, match="invalid Defender"):
        validate_worker_output(
            "defender",
            "case-a",
            {
                "role": "defender",
                "case_id": "case-a",
                "verdict": "majority_wins",
                "counterexamples": [],
                "false_positive_risks": [],
                "missing_evidence": [],
                "confidence": 0.5,
            },
        )


def test_hermes_profiles_require_separate_endpoint_and_key(monkeypatch) -> None:
    monkeypatch.setenv("SERGEANT_LEARNING_BACKEND", "hermes")
    monkeypatch.delenv("SERGEANT_HERMES_TEACHER_URL", raising=False)
    monkeypatch.delenv("SERGEANT_HERMES_TEACHER_KEY", raising=False)
    with pytest.raises(LearningWorkerError, match="Teacher|teacher"):
        WorkerConfig.from_env("teacher")


def test_worker_request_accepts_openai_compatible_hermes_response(monkeypatch) -> None:
    output = {
        "role": "prosecutor",
        "case_id": "case-a",
        "claim": "the old order exposes invalid state",
        "root_cause": "state publication precedes validation",
        "evidence": ["src/runtime.py"],
        "competing_explanations_rejected": ["format-only change"],
        "confidence": 0.9,
    }

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": json.dumps(output)}}]}).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    result = worker_request(
        "prosecutor",
        {"case_id": "case-a", "fixing_diff": "diff"},
        config=WorkerConfig(
            role="prosecutor",
            backend="hermes",
            endpoint="http://127.0.0.1:8644/v1/chat/completions",
            token="secret",
            model="prosecutor",
        ),
    )
    assert result["root_cause"] == "state publication precedes validation"
    assert result["transport"]["endpoint_class"] == "isolated-hermes-profile"
