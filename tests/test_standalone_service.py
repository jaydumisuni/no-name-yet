from __future__ import annotations

import hashlib
import hmac
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from main_review.standalone import (
    SERVICE_CONTRACT,
    StandaloneApplication,
    StandaloneServiceError,
    StandaloneSettings,
    build_command_center_document,
    create_server,
    main,
    normalize_github_webhook,
    verify_github_webhook_signature,
)


def _token() -> str:
    return "service-" + ("a" * 32)


def _secret() -> str:
    return "webhook-" + ("b" * 32)


def _request(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict | str]:
    request_headers = dict(headers or {})
    body = None
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read().decode("utf-8")
            content_type = response.headers.get_content_type()
            return response.status, json.loads(raw) if content_type == "application/json" else raw
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8")
        return error.code, json.loads(raw) if raw else {}


def _start_server(settings: StandaloneSettings, review_handler):
    server = create_server(settings, review_handler=review_handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, thread, f"http://127.0.0.1:{port}"


def test_settings_are_loopback_safe_and_require_auth_when_exposed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    loopback = StandaloneSettings.build(tmp_path, host="127.0.0.1", port=0, auth_token_env="", webhook_secret_env="")
    assert loopback.auth_token is None
    assert loopback.public_dict()["authentication"] == "loopback-trust"

    monkeypatch.delenv("TEST_SERVICE_TOKEN", raising=False)
    with pytest.raises(StandaloneServiceError, match="Non-loopback binding requires"):
        StandaloneSettings.build(tmp_path, host="0.0.0.0", port=8765, auth_token_env="TEST_SERVICE_TOKEN", webhook_secret_env="")

    monkeypatch.setenv("TEST_SERVICE_TOKEN", _token())
    remote = StandaloneSettings.build(tmp_path, host="0.0.0.0", port=8765, auth_token_env="TEST_SERVICE_TOKEN", webhook_secret_env="")
    assert remote.auth_token == _token()
    assert remote.public_dict()["authority"]["github_write"] is False
    assert remote.public_dict()["authority"]["executes_pr_code"] is False


def test_settings_reject_short_secrets_bad_origins_and_unbounded_limits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHORT_TOKEN", "too-short")
    with pytest.raises(StandaloneServiceError, match="at least 16"):
        StandaloneSettings.build(tmp_path, auth_token_env="SHORT_TOKEN", webhook_secret_env="")

    monkeypatch.setenv("GOOD_TOKEN", _token())
    monkeypatch.setenv("SHORT_WEBHOOK", "short")
    with pytest.raises(StandaloneServiceError, match="webhook secret"):
        StandaloneSettings.build(tmp_path, auth_token_env="GOOD_TOKEN", webhook_secret_env="SHORT_WEBHOOK")
    with pytest.raises(StandaloneServiceError, match="plain HTTP"):
        StandaloneSettings.build(tmp_path, auth_token_env="GOOD_TOKEN", webhook_secret_env="", allowed_origins=["https://example.com/path"])
    with pytest.raises(StandaloneServiceError, match="Maximum request size"):
        StandaloneSettings.build(tmp_path, auth_token_env="GOOD_TOKEN", webhook_secret_env="", max_request_bytes=10)
    with pytest.raises(StandaloneServiceError, match="Rate limit"):
        StandaloneSettings.build(tmp_path, auth_token_env="GOOD_TOKEN", webhook_secret_env="", rate_limit_per_minute=0)


def test_command_center_build_uses_existing_ui_and_real_standalone_bridge() -> None:
    document = build_command_center_document()

    assert "SERGEANT V2 — Command Center" in document
    assert "window.sergeantHostSend" in document
    assert "Read-only PR intake" in document
    assert "No automatic posting" in document
    assert "SERGEANT_CSS" not in document
    assert "SERGEANT_JS" not in document
    assert "SERGEANT_HOST_BOOTSTRAP" not in document
    assert "Standalone preview mode" in document  # fallback remains present but is bypassed by the injected host bridge.


def test_application_forces_workspace_read_only_and_no_learning_write(tmp_path: Path) -> None:
    captured: list[dict] = []

    def fake_review(request: dict) -> dict:
        captured.append(request)
        return {"ok": True, "action": "APPROVE", "top_findings": []}

    app = StandaloneApplication(
        StandaloneSettings.build(tmp_path, port=0, auth_token_env="", webhook_secret_env=""),
        review_handler=fake_review,
    )
    result = app.execute_review(
        {
            "root": "/tmp/escape",
            "mode": "repository",
            "write_learning": True,
            "execution_permissions": {"allow_write": True, "allow_shell": True, "allow_untrusted_code": True},
        }
    )

    assert captured[0]["root"] == str(tmp_path.resolve())
    assert captured[0]["write_learning"] is False
    assert captured[0]["execution_permissions"] == {
        "read_only": True,
        "allow_network": False,
        "allow_shell": False,
        "allow_write": False,
        "allow_untrusted_code": False,
    }
    assert result["mission"]["summary"]["verdict"] == "APPROVE"
    assert result["state"]["running"] is False
    assert app.runtime.review_count == 1


def test_current_and_changed_file_missions_require_contained_paths(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    app = StandaloneApplication(
        StandaloneSettings.build(tmp_path, port=0, auth_token_env="", webhook_secret_env=""),
        review_handler=lambda request: {"ok": True, "action": "COMMENT", "request": request},
    )

    with pytest.raises(StandaloneServiceError, match="requires"):
        app.execute_mission({"action": "reviewCurrentFile"})
    with pytest.raises(Exception):
        app.execute_mission({"action": "reviewCurrentFile", "current_file": "../escape.py"})

    result = app.execute_mission({"action": "reviewCurrentFile", "current_file": "src/app.py"})
    assert result["mission"]["payload"]["request"]["changed_files"] == ["src/app.py"]


def test_webhook_signature_and_pr_identity_are_verified() -> None:
    payload = {
        "action": "opened",
        "number": 12,
        "repository": {"full_name": "owner/repo"},
        "pull_request": {
            "number": 12,
            "base": {"ref": "main", "sha": "base", "repo": {"full_name": "owner/repo"}},
            "head": {"ref": "feature", "sha": "head", "repo": {"full_name": "fork/repo"}},
        },
    }
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = "sha256=" + hmac.new(_secret().encode("utf-8"), body, hashlib.sha256).hexdigest()

    assert verify_github_webhook_signature(_secret(), body, signature) is True
    assert verify_github_webhook_signature(_secret(), body, "sha256=bad") is False
    normalized = normalize_github_webhook("pull_request", payload, "delivery-1")
    assert normalized["accepted"] is True
    assert normalized["repository"] == "owner/repo"
    assert normalized["pull_request"] == 12
    assert normalized["authority"] == "intake-only-no-posting"
    assert normalized["review_request"]["execution_permissions"]["allow_write"] is False

    payload["pull_request"]["base"]["repo"]["full_name"] = "other/repo"
    with pytest.raises(StandaloneServiceError, match="base repository"):
        normalize_github_webhook("pull_request", payload, "delivery-2")


def test_http_service_proves_auth_ui_review_settings_and_webhook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_SERVICE_TOKEN", _token())
    monkeypatch.setenv("TEST_WEBHOOK_SECRET", _secret())
    settings = StandaloneSettings.build(
        tmp_path,
        host="127.0.0.1",
        port=0,
        auth_token_env="TEST_SERVICE_TOKEN",
        webhook_secret_env="TEST_WEBHOOK_SECRET",
        rate_limit_per_minute=100,
    )
    captured: list[dict] = []

    def fake_review(request: dict) -> dict:
        captured.append(request)
        return {"ok": True, "action": "APPROVE", "top_findings": [{"message": "Grounded proof"}]}

    server, thread, base = _start_server(settings, fake_review)
    try:
        status, health = _request(f"{base}/health")
        assert status == 200
        assert health["status"] == "ready"

        status, html = _request(f"{base}/")
        assert status == 200
        assert "SERGEANT V2 — Command Center" in html

        status, unauthorized = _request(f"{base}/api/v1/state")
        assert status == 401
        assert unauthorized["error"] == "authentication_required"

        status, state = _request(f"{base}/api/v1/state", token=_token())
        assert status == 200
        assert state["platform"] == "Self-hosted"
        assert state["running"] is False

        status, origin_denied = _request(
            f"{base}/api/v1/state",
            token=_token(),
            headers={"Origin": "https://evil.example"},
        )
        assert status == 403
        assert origin_denied["error"] == "origin_not_allowed"

        status, mission = _request(
            f"{base}/api/v1/review",
            method="POST",
            token=_token(),
            payload={"mode": "repository", "root": "/tmp/not-used", "write_learning": True},
        )
        assert status == 200
        assert mission["mission"]["summary"]["verdict"] == "APPROVE"
        assert mission["state"]["running"] is False
        assert captured[0]["root"] == str(tmp_path.resolve())
        assert captured[0]["write_learning"] is False

        status, settings_result = _request(
            f"{base}/api/v1/settings",
            method="POST",
            token=_token(),
            payload={"settings": {"policy": "required", "maxRounds": 4, "maxMembers": 7}},
        )
        assert status == 200
        assert settings_result["settings"]["policy"] == "required"
        assert settings_result["settings"]["maxRounds"] == 4

        ping = {"zen": "Keep it logically awesome."}
        ping_body = json.dumps(ping).encode("utf-8")
        signature = "sha256=" + hmac.new(_secret().encode("utf-8"), ping_body, hashlib.sha256).hexdigest()
        request = urllib.request.Request(
            f"{base}/api/v1/github/webhook",
            data=ping_body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "ping",
                "X-GitHub-Delivery": "delivery-http-1",
                "X-Hub-Signature-256": signature,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            webhook = json.loads(response.read().decode("utf-8"))
            assert response.status == 202
        assert webhook["accepted"] is True

        with urllib.request.urlopen(request, timeout=5) as response:
            duplicate = json.loads(response.read().decode("utf-8"))
            assert response.status == 200
        assert duplicate["duplicate"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_service_enforces_request_size_and_rate_limit(tmp_path: Path) -> None:
    settings = StandaloneSettings.build(
        tmp_path,
        host="127.0.0.1",
        port=0,
        auth_token_env="",
        webhook_secret_env="",
        max_request_bytes=1024,
        rate_limit_per_minute=2,
    )
    server, thread, base = _start_server(settings, lambda request: {"ok": True, "action": "APPROVE"})
    try:
        assert _request(f"{base}/health")[0] == 200
        assert _request(f"{base}/health")[0] == 200
        assert _request(f"{base}/health")[0] == 429
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_standalone_cli_check_validates_resources_without_binding(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--workspace", str(tmp_path), "--port", "0", "--token-env", "", "--webhook-secret-env", "", "--check"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["configuration"]["authority"]["auto_merge"] is False
    assert payload["capabilities"]["deployment"] == "self-hosted"
    assert payload["capabilities"]["schema_version"] == SERVICE_CONTRACT


def test_packaging_and_container_contracts_include_hardened_standalone_service() -> None:
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    compose = (root / "compose.yaml").read_text(encoding="utf-8")

    assert 'sergeant-serve = "main_review.standalone:main"' in pyproject
    assert '"share/sergeant/resources"' in pyproject
    assert '"resources/sergeant-standalone-host.js"' in pyproject
    assert "USER sergeant" in dockerfile
    assert 'CMD ["--workspace", "/workspace", "--host", "0.0.0.0", "--port", "8765"]' in dockerfile
    assert "read_only: true" in compose
    assert "cap_drop:" in compose and "- ALL" in compose
    assert "no-new-privileges:true" in compose
    assert "./:/workspace:ro" in compose
