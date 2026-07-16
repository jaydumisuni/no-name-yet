from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/cloudflare-full-council-certification.yml")
ASSURANCE = Path("docs/43-full-cloudflare-council-workflow-assurance.md")
REQUIRED_MODELS = {
    "@cf/zai-org/glm-4.7-flash",
    "@cf/qwen/qwen2.5-coder-32b-instruct",
    "@cf/ibm-granite/granite-4.0-h-micro",
    "@cf/openai/gpt-oss-120b",
    "@cf/moonshotai/kimi-k2.7-code",
    "@cf/qwen/qwen3-30b-a3b-fp8",
    "@cf/openai/gpt-oss-20b",
}


def test_candidate_validation_has_no_cloudflare_provider_values() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    validation, live = text.split("  certify-approved-candidate:", 1)

    assert "tests/test_cloudflare_incremental_certification.py" in validation
    assert "SERGEANT_CLOUDFLARE_ACCOUNT_ID" not in validation
    assert "SERGEANT_CLOUDFLARE_API_TOKEN" not in validation
    assert "environment: sergeant-cloudflare-certification" in live
    assert "SERGEANT_CLOUDFLARE_LIVE_CERTIFICATION_ENABLED" in live


def test_workflow_enforces_exact_seven_member_set() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    for model in REQUIRED_MODELS:
        assert model in text
    assert "set(payload.get('certified_models', [])) == required" in text


def test_workflow_has_machine_readable_assurance() -> None:
    text = ASSURANCE.read_text(encoding="utf-8").lower()

    assert ".github/workflows/cloudflare-full-council-certification.yml" in text
    for term in ("purpose", "permissions", "secrets", "rollback", "proof"):
        assert term in text
