from __future__ import annotations

from pathlib import Path


JOB_LEVEL_CONTEXT_TARGETS = (
    Path(".github/workflows/blind-static-training.yml"),
    Path(".github/workflows/review-intelligence-proof.yml"),
)


def test_runner_only_context_is_not_used_in_target_job_environment() -> None:
    for path in JOB_LEVEL_CONTEXT_TARGETS:
        text = path.read_text(encoding="utf-8")
        assert "SERGEANT_CLOUDFLARE_USAGE_STATE: ${{ runner.temp }}" not in text


def test_static_training_uses_runner_temp_only_after_runner_start() -> None:
    path = Path(".github/workflows/blind-static-training.yml")
    text = path.read_text(encoding="utf-8")
    assert (
        'run: echo "SERGEANT_CLOUDFLARE_USAGE_STATE=${RUNNER_TEMP}/sergeant-training-usage.json" '
        '>> "$GITHUB_ENV"'
    ) in text
    export_at = text.index("Configure isolated Cloudflare usage state")
    training_at = text.index("Run Sergeant first without models or workspace")
    assert export_at < training_at


def test_review_intelligence_does_not_duplicate_static_training_job() -> None:
    text = Path(".github/workflows/review-intelligence-proof.yml").read_text(encoding="utf-8")
    assert "static-first-development-set:" not in text
    assert "Run Sergeant first without models or workspace" not in text
