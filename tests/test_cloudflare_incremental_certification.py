from __future__ import annotations

import json

from main_review import cloudflare_incremental_certification as incremental
from main_review.cloudflare_gateway import CloudflareGatewaySettings


MODELS = (
    incremental.GRANITE_MODEL,
    "@cf/qwen/qwen3-30b-a3b-fp8",
    "@cf/openai/gpt-oss-20b",
)


def _settings() -> CloudflareGatewaySettings:
    return CloudflareGatewaySettings(
        account_id="0123456789abcdef0123456789abcdef",
        api_token="secret",
        models=MODELS,
    )


def _certified(model: str) -> dict[str, object]:
    return {
        "model": model,
        "status": "certified",
        "structured_transport_passed": True,
        "role_mission_passed": True,
        "proof_type": "role_mission",
        "error_kind": "",
    }


def test_incremental_certification_skips_same_head_passes(monkeypatch, tmp_path) -> None:
    ledger_path = tmp_path / "ledger.json"
    ledger = incremental._fresh_ledger("abc123")
    ledger["members"][MODELS[0]] = _certified(MODELS[0])
    incremental.save_ledger(ledger_path, ledger)
    called: list[str] = []

    def fake_run(settings, *, model, root, auth_file, scout_file):
        called.append(model)
        return _certified(model)

    monkeypatch.setattr(incremental, "_run_member", fake_run)
    monkeypatch.setattr(incremental, "cloudflare_usage_status", lambda: {})

    result = incremental.certify_incrementally(
        _settings(),
        root=tmp_path,
        auth_file="src/auth.py",
        scout_file="src/scout.py",
        tested_sha="abc123",
        ledger_path=ledger_path,
    )

    assert result["passed"] is True
    assert result["skipped_models"] == [MODELS[0]]
    assert called == [MODELS[1], MODELS[2]]
    assert result["certified_member_count"] == 3


def test_quota_signal_stops_before_later_members(monkeypatch, tmp_path) -> None:
    ledger_path = tmp_path / "ledger.json"
    called: list[str] = []

    def fake_run(settings, *, model, root, auth_file, scout_file):
        called.append(model)
        return {
            "model": model,
            "status": "failed",
            "structured_transport_passed": False,
            "role_mission_passed": False,
            "error_kind": "http_429_code_4006_daily_allocation",
        }

    monkeypatch.setattr(incremental, "_run_member", fake_run)
    monkeypatch.setattr(incremental, "cloudflare_usage_status", lambda: {})

    result = incremental.certify_incrementally(
        _settings(),
        root=tmp_path,
        auth_file="src/auth.py",
        scout_file="src/scout.py",
        tested_sha="abc123",
        ledger_path=ledger_path,
    )

    assert called == [MODELS[0]]
    assert result["quota_blocked"] is True
    assert result["called_models"] == [MODELS[0]]
    assert result["members"][0]["status"] == "quota_blocked"


def test_same_day_quota_ledger_makes_no_calls(monkeypatch, tmp_path) -> None:
    ledger_path = tmp_path / "ledger.json"
    ledger = incremental._fresh_ledger("abc123")
    ledger["quota_blocked_day"] = incremental._utc_day()
    incremental.save_ledger(ledger_path, ledger)
    called: list[str] = []

    monkeypatch.setattr(
        incremental,
        "_run_member",
        lambda *args, **kwargs: called.append(str(kwargs.get("model"))) or {},
    )
    monkeypatch.setattr(incremental, "cloudflare_usage_status", lambda: {})

    result = incremental.certify_incrementally(
        _settings(),
        root=tmp_path,
        auth_file="src/auth.py",
        scout_file="src/scout.py",
        tested_sha="abc123",
        ledger_path=ledger_path,
    )

    assert called == []
    assert result["stopped_reason"] == "quota_blocked_until_next_utc_day"


def test_same_day_budget_ledger_makes_no_calls(monkeypatch, tmp_path) -> None:
    ledger_path = tmp_path / "ledger.json"
    ledger = incremental._fresh_ledger("abc123")
    ledger["budget_blocked"] = True
    ledger["budget_blocked_day"] = incremental._utc_day()
    incremental.save_ledger(ledger_path, ledger)
    called: list[str] = []

    monkeypatch.setattr(
        incremental,
        "_run_member",
        lambda *args, **kwargs: called.append(str(kwargs.get("model"))) or {},
    )
    monkeypatch.setattr(incremental, "cloudflare_usage_status", lambda: {})

    result = incremental.certify_incrementally(
        _settings(),
        root=tmp_path,
        auth_file="src/auth.py",
        scout_file="src/scout.py",
        tested_sha="abc123",
        ledger_path=ledger_path,
    )

    assert called == []
    assert result["stopped_reason"] == "local_budget_blocked"


def test_previous_day_budget_block_expires_and_resumes(monkeypatch, tmp_path) -> None:
    ledger_path = tmp_path / "ledger.json"
    ledger = incremental._fresh_ledger("abc123")
    ledger["budget_blocked"] = True
    ledger["budget_blocked_day"] = "2000-01-01"
    incremental.save_ledger(ledger_path, ledger)
    called: list[str] = []

    def fake_run(settings, *, model, root, auth_file, scout_file):
        called.append(model)
        return _certified(model)

    monkeypatch.setattr(incremental, "_run_member", fake_run)
    monkeypatch.setattr(incremental, "cloudflare_usage_status", lambda: {})

    result = incremental.certify_incrementally(
        _settings(),
        root=tmp_path,
        auth_file="src/auth.py",
        scout_file="src/scout.py",
        tested_sha="abc123",
        ledger_path=ledger_path,
    )

    assert called == list(MODELS)
    assert result["passed"] is True
    current = incremental.load_ledger(ledger_path, "abc123")
    assert current["budget_blocked"] is False
    assert current["budget_blocked_day"] == ""


def test_new_exact_head_discards_old_member_passes(tmp_path) -> None:
    ledger_path = tmp_path / "ledger.json"
    old = incremental._fresh_ledger("old-head")
    old["members"][MODELS[0]] = _certified(MODELS[0])
    incremental.save_ledger(ledger_path, old)

    current = incremental.load_ledger(ledger_path, "new-head")

    assert current["tested_sha"] == "new-head"
    assert current["members"] == {}


def test_saved_ledger_contains_no_credentials(tmp_path) -> None:
    ledger_path = tmp_path / "ledger.json"
    ledger = incremental._fresh_ledger("abc123")
    ledger["members"][MODELS[0]] = _certified(MODELS[0])
    incremental.save_ledger(ledger_path, ledger)

    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    text = json.dumps(payload)
    assert "secret" not in text
    assert "0123456789abcdef0123456789abcdef" not in text
