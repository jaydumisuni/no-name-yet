from __future__ import annotations

from pathlib import Path

import pytest

from main_review import cloudflare_cli, cloudflare_scout_qualification, llm_provider
from main_review.cloudflare_gateway import CloudflareGatewayError, CloudflareGatewaySettings


def _settings(models: tuple[str, ...] = ("@cf/test/model",)) -> CloudflareGatewaySettings:
    return CloudflareGatewaySettings(
        account_id="0123456789abcdef0123456789abcdef",
        api_token="secret-token",
        models=models,
        host="127.0.0.1",
        port=0,
        timeout_seconds=90.0,
        max_request_bytes=100_000,
    )


def test_structured_proof_rejects_echoed_required_instruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = "@cf/test/model"
    monkeypatch.setattr(
        cloudflare_cli,
        "invoke_json",
        lambda *args, **kwargs: {
            "required": {
                "status": "ready",
                "model": model,
                "capabilities": cloudflare_cli.REQUIRED_PROOF_CAPABILITIES,
            }
        },
    )

    result = cloudflare_cli.test_models(_settings())

    assert result["all_passed"] is False


def test_structured_proof_accepts_provider_result_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = "@cf/test/model"
    monkeypatch.setattr(
        cloudflare_cli,
        "invoke_json",
        lambda *args, **kwargs: {
            "result": {
                "status": "ready",
                "model": model,
                "capabilities": cloudflare_cli.REQUIRED_PROOF_CAPABILITIES,
            }
        },
    )

    assert cloudflare_cli.test_models(_settings())["all_passed"] is True


def test_security_coverage_accepts_specific_security_areas() -> None:
    assert cloudflare_cli._coverage_area_matches(
        "security",
        {
            "command injection",
            "shell execution",
            "trust boundary",
            "authentication/authorization",
        },
    ) is True


def test_security_coverage_rejects_ambiguous_substrings() -> None:
    assert cloudflare_cli._coverage_area_matches("security", {"source mapping"}) is False
    assert cloudflare_cli._coverage_area_matches("security", {"authoring workflow"}) is False


def test_json_parser_selects_final_review_object_from_reasoning_text() -> None:
    text = (
        'thinking {"verdict":"BLOCK","findings":[],"coverage":{"note":"verbose example"}} final '
        '{"verdict":"PASS","findings":[],"coverage":{}}'
    )
    assert llm_provider._parse_json_text(text)["verdict"] == "PASS"

    payload = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "reasoning_content": '{"status":"ready"}',
                }
            }
        ]
    }
    assert llm_provider._extract_text(payload, "chat_completions") == '{"status":"ready"}'


def test_scout_qualification_requires_exact_grounded_facts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    source = root / "src" / "scout.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        'RETRY_LIMIT = 3\n'
        'TIMEOUT_SECONDS = 15\n'
        'SUPPORTED_LANGUAGES = ["python", "javascript"]\n',
        encoding="utf-8",
    )
    model = "@cf/test/model"
    monkeypatch.setattr(
        cloudflare_scout_qualification,
        "invoke_json",
        lambda *args, **kwargs: {
            "status": "ready",
            "model": model,
            "coverage": {
                "files_reviewed": ["src/scout.py"],
                "areas": ["evidence extraction"],
            },
            "facts": [
                {"name": "RETRY_LIMIT", "value": 3, "line": 1},
                {"name": "TIMEOUT_SECONDS", "value": 15, "line": 2},
                {
                    "name": "SUPPORTED_LANGUAGES",
                    "value": ["python", "javascript"],
                    "line": 3,
                },
            ],
        },
    )

    result = cloudflare_scout_qualification.qualify_scouts(
        _settings(),
        root=root,
        file="src/scout.py",
    )

    assert result["all_passed"] is True


def test_scout_qualification_rejects_paths_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("SECRET = 1\n", encoding="utf-8")

    with pytest.raises(CloudflareGatewayError, match="remain inside"):
        cloudflare_scout_qualification.qualify_scouts(
            _settings(),
            root=root,
            file="../outside.py",
        )

    with pytest.raises(CloudflareGatewayError, match="remain inside"):
        cloudflare_scout_qualification.qualify_scouts(
            _settings(),
            root=root,
            file=str(outside.resolve()),
        )
