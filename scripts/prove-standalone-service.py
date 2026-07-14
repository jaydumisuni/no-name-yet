from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request_json(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> tuple[int, dict]:
    request_headers = dict(headers or {})
    body = None
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8")
        return error.code, json.loads(raw) if raw else {}


def request_text(url: str, *, timeout: int = 10) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8")


def wait_for_health(base_url: str, process: subprocess.Popen[str]) -> dict:
    deadline = time.monotonic() + 30
    last_error = "service did not respond"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Standalone service exited early with code {process.returncode}")
        try:
            status, payload = request_json(f"{base_url}/health", timeout=2)
            if status == 200 and payload.get("status") == "ready":
                return payload
        except Exception as error:  # noqa: BLE001 - proof loop captures the last transport error.
            last_error = str(error)
        time.sleep(0.2)
    raise RuntimeError(f"Standalone service health proof timed out: {last_error}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    build = root / "build"
    build.mkdir(exist_ok=True)
    proof_path = build / "standalone-service-proof.json"
    log_path = build / "standalone-service.log"
    token = secrets.token_urlsafe(32)
    webhook_secret = secrets.token_urlsafe(32)
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    environment = os.environ.copy()
    environment["SERGEANT_SERVICE_TOKEN"] = token
    environment["SERGEANT_WEBHOOK_SECRET"] = webhook_secret

    check = subprocess.run(
        [
            sys.executable,
            "-m",
            "main_review.standalone",
            "--workspace",
            str(root),
            "--port",
            "0",
            "--check",
        ],
        cwd=root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if check.returncode != 0:
        raise RuntimeError(f"Standalone configuration proof failed: {check.stdout}\n{check.stderr}")
    check_payload = json.loads(check.stdout)

    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "main_review.standalone",
                "--workspace",
                str(root),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--rate-limit",
                "300",
            ],
            cwd=root,
            env=environment,
            text=True,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            health = wait_for_health(base_url, process)
            unauthorized_status, unauthorized = request_json(f"{base_url}/api/v1/state")
            if unauthorized_status != 401 or unauthorized.get("error") != "authentication_required":
                raise AssertionError("Protected state endpoint accepted an unauthenticated request.")

            capabilities_status, capabilities = request_json(f"{base_url}/api/v1/capabilities", token=token)
            if capabilities_status != 200:
                raise AssertionError("Authenticated capability request failed.")
            if capabilities["configuration"]["authority"]["repository_write"] is not False:
                raise AssertionError("Standalone capability contract unexpectedly grants repository write authority.")
            if capabilities["github_webhook"]["posting"] is not False:
                raise AssertionError("Standalone capability contract unexpectedly grants GitHub posting authority.")

            html_status, html = request_text(f"{base_url}/")
            if html_status != 200 or "SERGEANT V2 — Command Center" not in html or "window.sergeantHostSend" not in html:
                raise AssertionError("Packaged Command Center did not render with the standalone bridge.")

            mission_status, mission = request_json(
                f"{base_url}/api/v1/missions",
                method="POST",
                token=token,
                payload={"action": "reviewCurrentFile", "current_file": "main_review/standalone.py"},
                timeout=120,
            )
            if mission_status != 200 or not mission.get("mission", {}).get("mission_id"):
                raise AssertionError("Standalone review mission did not produce a mission record.")
            if mission.get("state", {}).get("running") is not False:
                raise AssertionError("Standalone service remained locked after mission completion.")

            ping = {"zen": "Keep it logically awesome."}
            ping_body = json.dumps(ping).encode("utf-8")
            signature = "sha256=" + hmac.new(webhook_secret.encode("utf-8"), ping_body, hashlib.sha256).hexdigest()
            webhook_request = urllib.request.Request(
                f"{base_url}/api/v1/github/webhook",
                data=ping_body,
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Event": "ping",
                    "X-GitHub-Delivery": "standalone-proof-delivery",
                    "X-Hub-Signature-256": signature,
                },
                method="POST",
            )
            with urllib.request.urlopen(webhook_request, timeout=10) as response:
                webhook_status = response.status
                webhook = json.loads(response.read().decode("utf-8"))
            if webhook_status != 202 or webhook.get("accepted") is not True:
                raise AssertionError("Signed GitHub webhook was not accepted.")
            with urllib.request.urlopen(webhook_request, timeout=10) as response:
                duplicate_status = response.status
                duplicate = json.loads(response.read().decode("utf-8"))
            if duplicate_status != 200 or duplicate.get("duplicate") is not True:
                raise AssertionError("Webhook replay suppression did not identify a duplicate delivery.")

            state_status, state = request_json(f"{base_url}/api/v1/state", token=token)
            if state_status != 200 or state.get("service", {}).get("reviews", 0) < 1:
                raise AssertionError("Standalone state did not preserve the completed mission.")

            proof = {
                "proof_version": "sergeant.standalone-proof.v1",
                "service_contract": capabilities["schema_version"],
                "configuration_check": check_payload.get("ok") is True,
                "health": health.get("status"),
                "unauthenticated_state_status": unauthorized_status,
                "authenticated_capabilities_status": capabilities_status,
                "command_center_status": html_status,
                "command_center_bridge": "window.sergeantHostSend" in html,
                "mission_status": mission_status,
                "mission_id": mission["mission"]["mission_id"],
                "mission_verdict": mission["mission"]["summary"]["verdict"],
                "mission_lock_released": mission["state"]["running"] is False,
                "webhook_status": webhook_status,
                "webhook_duplicate_status": duplicate_status,
                "webhook_replay_suppressed": duplicate.get("duplicate") is True,
                "repository_write": capabilities["configuration"]["authority"]["repository_write"],
                "github_write": capabilities["configuration"]["authority"]["github_write"],
                "executes_pr_code": capabilities["configuration"]["authority"]["executes_pr_code"],
                "requests_recorded": state["service"]["requests"],
                "reviews_recorded": state["service"]["reviews"],
                "webhooks_recorded": state["service"]["webhooks"],
                "verdict": "PASS",
            }
            proof_text = json.dumps(proof, indent=2, sort_keys=True) + "\n"
            if token in proof_text or webhook_secret in proof_text:
                raise AssertionError("Standalone proof artifact contains a service secret.")
            proof_path.write_text(proof_text, encoding="utf-8")
            print(proof_text, end="")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    if token in log_text or webhook_secret in log_text:
        raise AssertionError("Standalone service log contains a service secret.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
