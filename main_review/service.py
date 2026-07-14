"""Dependency-free self-hosted runtime for Sergeant.

The runtime exposes Sergeant through a bounded HTTP service while preserving the
reviewer's authority separation. It never grants repository writes, GitHub
posting, pull-request code execution, patch application, or automatic merge.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import os
import sysconfig
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from .app_bridge import handle_app_review_request
from .battle_tests import validate_battle_fixtures
from .final_proof import run_final_proof
from .hardened_mission import run_v2_mission
from .ide_bench import build_ide_bench_contract
from .production_hardening import (
    HardeningError,
    normalize_changed_files,
    redact_secrets,
    validate_repository_slug,
)

SERVICE_CONTRACT = "sergeant.standalone.v1"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_MAX_REQUEST_BYTES = 1_048_576
DEFAULT_RATE_LIMIT = 60
MAX_HISTORY = 20
_ALLOWED_MISSIONS = {
    "reviewWorkspace",
    "reviewCurrentFile",
    "reviewChangedFiles",
    "finalProof",
    "battleTests",
    "ideBenchContract",
    "v2Mission",
}


class StandaloneServiceError(ValueError):
    """Raised when service configuration or untrusted input is unsafe."""


class StandaloneServiceBusy(RuntimeError):
    """Raised when a second mission overlaps an active mission."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_loopback_host(host: str) -> bool:
    value = str(host or "").strip().lower()
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _secret_from_env(name: str | None) -> str | None:
    env_name = str(name or "").strip()
    if not env_name:
        return None
    if not env_name.replace("_", "A").isalnum() or env_name[0].isdigit():
        raise StandaloneServiceError(f"Invalid environment variable name: {env_name!r}")
    return os.getenv(env_name) or None


@dataclass(frozen=True)
class StandaloneSettings:
    workspace_root: Path
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    auth_token: str | None = None
    webhook_secret: str | None = None
    allowed_origins: tuple[str, ...] = ()
    max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES
    rate_limit_per_minute: int = DEFAULT_RATE_LIMIT
    command_center_enabled: bool = True

    @classmethod
    def build(
        cls,
        workspace_root: str | Path = ".",
        *,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        auth_token_env: str | None = "SERGEANT_SERVICE_TOKEN",
        webhook_secret_env: str | None = "SERGEANT_WEBHOOK_SECRET",
        allowed_origins: tuple[str, ...] | list[str] = (),
        max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES,
        rate_limit_per_minute: int = DEFAULT_RATE_LIMIT,
        command_center_enabled: bool = True,
    ) -> "StandaloneSettings":
        settings = cls(
            workspace_root=Path(workspace_root).resolve(),
            host=str(host or DEFAULT_HOST).strip(),
            port=int(port),
            auth_token=_secret_from_env(auth_token_env),
            webhook_secret=_secret_from_env(webhook_secret_env),
            allowed_origins=tuple(str(item).strip().rstrip("/") for item in allowed_origins if str(item).strip()),
            max_request_bytes=int(max_request_bytes),
            rate_limit_per_minute=int(rate_limit_per_minute),
            command_center_enabled=bool(command_center_enabled),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.workspace_root.exists() or not self.workspace_root.is_dir():
            raise StandaloneServiceError(f"Workspace root must be an existing directory: {self.workspace_root}")
        if not self.host:
            raise StandaloneServiceError("Service host must be non-empty.")
        if not 0 <= self.port <= 65535:
            raise StandaloneServiceError("Service port must be between 0 and 65535.")
        if not 1_024 <= self.max_request_bytes <= 16 * 1_048_576:
            raise StandaloneServiceError("Maximum request size must be between 1 KiB and 16 MiB.")
        if not 1 <= self.rate_limit_per_minute <= 10_000:
            raise StandaloneServiceError("Rate limit must be between 1 and 10,000 requests per minute.")
        if self.auth_token is not None and len(self.auth_token) < 16:
            raise StandaloneServiceError("Service authentication token must contain at least 16 characters.")
        if not _is_loopback_host(self.host):
            if not self.auth_token:
                raise StandaloneServiceError(
                    "Non-loopback binding requires SERGEANT_SERVICE_TOKEN or another configured auth-token environment variable."
                )
            if len(self.auth_token) < 24:
                raise StandaloneServiceError(
                    "Service authentication token must contain at least 24 characters for non-loopback binding."
                )
        if self.webhook_secret is not None and len(self.webhook_secret) < 24:
            raise StandaloneServiceError("GitHub webhook secret must contain at least 24 characters.")
        for origin in self.allowed_origins:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"}:
                raise StandaloneServiceError(f"Allowed origin must be a plain HTTP(S) origin: {origin!r}")

    def public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SERVICE_CONTRACT,
            "workspace_root": str(self.workspace_root),
            "host": self.host,
            "port": self.port,
            "authentication": "bearer-token" if self.auth_token else "loopback-trust",
            "webhook_intake": "enabled" if self.webhook_secret else "disabled",
            "allowed_origins": list(self.allowed_origins),
            "max_request_bytes": self.max_request_bytes,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "command_center_enabled": self.command_center_enabled,
            "authority": {
                "repository_write": False,
                "github_write": False,
                "executes_pr_code": False,
                "auto_merge": False,
            },
        }


@dataclass
class StandaloneRuntime:
    settings: StandaloneSettings
    started_monotonic: float = field(default_factory=time.monotonic)
    started_at: str = field(default_factory=_utc_now)
    request_count: int = 0
    review_count: int = 0
    webhook_count: int = 0
    last_result: dict[str, Any] | None = None
    history: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=MAX_HISTORY))
    recent_deliveries: deque[str] = field(default_factory=lambda: deque(maxlen=500))
    review_lock: threading.Lock = field(default_factory=threading.Lock)
    state_lock: threading.Lock = field(default_factory=threading.Lock)
    rate_windows: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))
    ui_settings: dict[str, Any] = field(
        default_factory=lambda: {
            "policy": "preferred",
            "provider": "auto",
            "baseUrl": "",
            "model": "",
            "protocol": "auto",
            "council": "adaptive",
            "maxRounds": 2,
            "maxMembers": 5,
        }
    )

    def record_request(self) -> None:
        with self.state_lock:
            self.request_count += 1

    def rate_allowed(self, client: str) -> bool:
        now = time.monotonic()
        cutoff = now - 60
        with self.state_lock:
            window = self.rate_windows[client]
            while window and window[0] < cutoff:
                window.popleft()
            if len(window) >= self.settings.rate_limit_per_minute:
                return False
            window.append(now)
            return True

    def remember_delivery(self, delivery: str) -> bool:
        with self.state_lock:
            if delivery in self.recent_deliveries:
                return False
            self.recent_deliveries.append(delivery)
            self.webhook_count += 1
            return True

    def update_ui_settings(self, supplied: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {"policy", "provider", "baseUrl", "model", "protocol", "council", "maxRounds", "maxMembers"}
        unknown = sorted(set(supplied) - allowed)
        if unknown:
            raise StandaloneServiceError(f"Unknown Command Center setting keys: {', '.join(unknown)}")
        updated = dict(self.ui_settings)
        for key in {"policy", "provider", "baseUrl", "model", "protocol", "council"}:
            if key in supplied:
                updated[key] = str(supplied[key] or "")[:500]
        if "maxRounds" in supplied:
            updated["maxRounds"] = max(1, min(6, int(supplied["maxRounds"])))
        if "maxMembers" in supplied:
            updated["maxMembers"] = max(1, min(12, int(supplied["maxMembers"])))
        with self.state_lock:
            self.ui_settings = updated
            return dict(self.ui_settings)

    def record_mission(self, mission: dict[str, Any]) -> None:
        with self.state_lock:
            self.review_count += 1
            self.last_result = mission
            self.history.appendleft(
                {
                    "id": mission.get("mission_id"),
                    "date": mission.get("finished_at"),
                    "result": mission.get("summary", {}).get("verdict"),
                    "mission": mission.get("title"),
                    "duration": f"{mission.get('duration_ms', 0)} ms",
                }
            )

    def snapshot(self) -> dict[str, Any]:
        with self.state_lock:
            return {
                "schema_version": SERVICE_CONTRACT,
                "status": "Reviewing" if self.review_lock.locked() else "Standing By",
                "workspace": self.settings.workspace_root.name,
                "workspaceRoot": str(self.settings.workspace_root),
                "branch": _read_git_branch(self.settings.workspace_root),
                "changedFilesCount": 0,
                "platform": "Self-hosted",
                "running": self.review_lock.locked(),
                "progress": 42 if self.review_lock.locked() else 100 if self.last_result else 0,
                "last": self.last_result,
                "history": list(self.history),
                "settings": dict(self.ui_settings),
                "service": {
                    "started_at": self.started_at,
                    "uptime_seconds": round(time.monotonic() - self.started_monotonic, 3),
                    "requests": self.request_count,
                    "reviews": self.review_count,
                    "webhooks": self.webhook_count,
                },
            }


def _read_git_branch(root: Path) -> str:
    try:
        value = (root / ".git" / "HEAD").read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return "—"
    prefix = "ref: refs/heads/"
    return value[len(prefix) :] if value.startswith(prefix) else value[:12] or "—"


def verify_github_webhook_signature(secret: str, body: bytes, signature: str | None) -> bool:
    supplied = str(signature or "").strip()
    if not supplied.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied)


def normalize_github_webhook(event: str, payload: Mapping[str, Any], delivery: str) -> dict[str, Any]:
    event_name = str(event or "").strip().lower()
    delivery_id = str(delivery or "").strip()
    if not delivery_id or len(delivery_id) > 200:
        raise StandaloneServiceError("GitHub webhook delivery identifier is missing or invalid.")
    if event_name == "ping":
        return {
            "schema_version": SERVICE_CONTRACT,
            "accepted": True,
            "event": "ping",
            "delivery": delivery_id,
            "zen": str(payload.get("zen") or "")[:200],
        }
    if event_name != "pull_request":
        raise StandaloneServiceError(f"Unsupported GitHub webhook event: {event_name!r}")

    action = str(payload.get("action") or "").strip()
    if action not in {"opened", "synchronize", "reopened", "ready_for_review"}:
        return {
            "schema_version": SERVICE_CONTRACT,
            "accepted": False,
            "ignored": True,
            "event": event_name,
            "action": action,
            "delivery": delivery_id,
            "reason": "Pull-request action does not require a new review.",
        }

    repository_payload = payload.get("repository") if isinstance(payload.get("repository"), Mapping) else {}
    pull_request = payload.get("pull_request") if isinstance(payload.get("pull_request"), Mapping) else {}
    base = pull_request.get("base") if isinstance(pull_request.get("base"), Mapping) else {}
    head = pull_request.get("head") if isinstance(pull_request.get("head"), Mapping) else {}
    base_repo = base.get("repo") if isinstance(base.get("repo"), Mapping) else {}
    repository = validate_repository_slug(str(repository_payload.get("full_name") or ""))
    if str(base_repo.get("full_name") or "") != repository:
        raise StandaloneServiceError("Webhook pull-request base repository does not match the repository payload.")
    try:
        number = int(pull_request.get("number") or payload.get("number"))
    except (TypeError, ValueError) as error:
        raise StandaloneServiceError("Webhook pull request number is invalid.") from error
    if number <= 0:
        raise StandaloneServiceError("Webhook pull request number must be positive.")
    return {
        "schema_version": SERVICE_CONTRACT,
        "accepted": True,
        "event": event_name,
        "action": action,
        "delivery": delivery_id,
        "repository": repository,
        "pull_request": number,
        "base": {"ref": base.get("ref"), "sha": base.get("sha")},
        "head": {"ref": head.get("ref"), "sha": head.get("sha")},
        "review_request": {
            "mode": "pull_request",
            "source": "github-webhook",
            "pull_request": {
                "repository": repository,
                "number": number,
                "base_sha": base.get("sha"),
                "head_sha": head.get("sha"),
            },
            "execution_permissions": {
                "read_only": True,
                "allow_network": False,
                "allow_shell": False,
                "allow_write": False,
                "allow_untrusted_code": False,
            },
        },
        "authority": "intake-only-no-posting",
    }


def _resource_roots() -> list[Path]:
    roots: list[Path] = []
    override = os.getenv("SERGEANT_COMMAND_CENTER_ROOT")
    if override:
        roots.append(Path(override).expanduser().resolve())
    roots.append(Path(__file__).resolve().parents[1] / "resources")
    roots.append(Path(sysconfig.get_path("data")) / "share" / "sergeant" / "resources")
    return list(dict.fromkeys(roots))


def _read_resource(name: str) -> str:
    for root in _resource_roots():
        path = root / name
        if path.is_file():
            return path.read_text(encoding="utf-8")
    searched = ", ".join(str(root) for root in _resource_roots())
    raise StandaloneServiceError(f"Command Center resource {name!r} was not found. Searched: {searched}")


def build_command_center_document() -> str:
    html = _read_resource("sergeant-command-center-v2.html")
    css = _read_resource("sergeant-command-center-v2.css")
    responsive = _read_resource("sergeant-command-center-v2-responsive.css")
    script = _read_resource("sergeant-command-center-v2.js").replace(
        "github: ['Repository status', 'PR comments planned', 'Commit evidence']",
        "github: ['Read-only PR intake', 'Verified webhook events', 'No automatic posting']",
    )
    host = _read_resource("sergeant-standalone-host.js")
    document = (
        html.replace("/* SERGEANT_CSS */", css)
        .replace("/* SERGEANT_RESPONSIVE_CSS */", responsive)
        .replace("// SERGEANT_JS", script)
        .replace("<!-- SERGEANT_HOST_BOOTSTRAP -->", f"<script>{host}</script>")
    )
    if any(marker in document for marker in ("SERGEANT_CSS", "SERGEANT_JS", "SERGEANT_HOST_BOOTSTRAP")):
        raise StandaloneServiceError("Command Center build left unresolved resource placeholders.")
    return document


def _verdict(payload: Mapping[str, Any]) -> str:
    action = payload.get("action")
    if isinstance(action, str) and action:
        return action
    nested = payload.get("verdict")
    if isinstance(nested, Mapping) and isinstance(nested.get("verdict"), str):
        return str(nested["verdict"])
    if isinstance(nested, str) and nested:
        return nested
    if payload.get("passed") is True or payload.get("ok") is True:
        return "PASS"
    if payload.get("passed") is False or payload.get("ok") is False:
        return "NEEDS WORK"
    return "REPORT READY"


def _findings(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    direct = payload.get("top_findings")
    if isinstance(direct, list):
        return [item for item in direct if isinstance(item, dict)][:20]
    packet = payload.get("packet")
    if isinstance(packet, Mapping):
        intelligence = packet.get("review_intelligence")
        if isinstance(intelligence, Mapping) and isinstance(intelligence.get("ranked_findings"), list):
            return [item for item in intelligence["ranked_findings"] if isinstance(item, dict)][:20]
    return []


ReviewHandler = Callable[[dict[str, Any]], dict[str, Any]]


class StandaloneApplication:
    def __init__(self, settings: StandaloneSettings, *, review_handler: ReviewHandler = handle_app_review_request) -> None:
        self.settings = settings
        self.runtime = StandaloneRuntime(settings)
        self.review_handler = review_handler
        self._command_center: bytes | None = None

    def capabilities(self) -> dict[str, Any]:
        return {
            "schema_version": SERVICE_CONTRACT,
            "service": "Sergeant",
            "deployment": "self-hosted",
            "endpoints": {
                "health": "GET /health",
                "capabilities": "GET /api/v1/capabilities",
                "state": "GET /api/v1/state",
                "review": "POST /api/v1/review",
                "missions": "POST /api/v1/missions",
                "settings": "POST /api/v1/settings",
                "latest_report": "GET /api/v1/reports/latest",
                "github_webhook": "POST /api/v1/github/webhook",
                "command_center": "GET /",
            },
            "missions": sorted(_ALLOWED_MISSIONS),
            "configuration": self.settings.public_dict(),
            "github_webhook": {
                "enabled": bool(self.settings.webhook_secret),
                "events": ["ping", "pull_request"],
                "pull_request_actions": ["opened", "synchronize", "reopened", "ready_for_review"],
                "posting": False,
                "auto_review": False,
            },
        }

    def command_center(self) -> bytes:
        if not self.settings.command_center_enabled:
            raise StandaloneServiceError("Command Center is disabled for this service instance.")
        if self._command_center is None:
            self._command_center = build_command_center_document().encode("utf-8")
        return self._command_center

    def execute_review(self, supplied: Mapping[str, Any]) -> dict[str, Any]:
        request = dict(supplied)
        request["root"] = str(self.settings.workspace_root)
        request["write_learning"] = False
        request["source"] = f"standalone:{str(request.get('source') or 'api')[:100]}"
        request["execution_permissions"] = {
            "read_only": True,
            "allow_network": False,
            "allow_shell": False,
            "allow_write": False,
            "allow_untrusted_code": False,
        }
        if request.get("changed_files"):
            request["changed_files"] = normalize_changed_files(self.settings.workspace_root, request["changed_files"])
        return self._run_locked("Standalone Review", lambda: self.review_handler(request))

    def execute_mission(self, supplied: Mapping[str, Any]) -> dict[str, Any]:
        action = str(supplied.get("action") or "").strip()
        if action not in _ALLOWED_MISSIONS:
            raise StandaloneServiceError(f"Unknown standalone mission action: {action!r}")
        if action == "reviewWorkspace":
            return self.execute_review({"mode": "repository", "changed_files": [], "source": "command-center:workspace"})
        if action == "reviewCurrentFile":
            current = str(supplied.get("current_file") or "").strip()
            if not current:
                raise StandaloneServiceError("Current-file review requires a repository-relative current_file value.")
            files = normalize_changed_files(self.settings.workspace_root, [current])
            return self.execute_review({"mode": "changed_files", "changed_files": files, "source": "command-center:current-file"})
        if action == "reviewChangedFiles":
            changed = supplied.get("changed_files")
            if not isinstance(changed, list) or not changed:
                raise StandaloneServiceError("Changed-files review requires a non-empty changed_files list.")
            files = normalize_changed_files(self.settings.workspace_root, changed)
            return self.execute_review({"mode": "changed_files", "changed_files": files, "source": "command-center:changed-files"})
        if action == "finalProof":
            return self._run_locked("Final Proof", lambda: run_final_proof(self.settings.workspace_root))
        if action == "battleTests":
            return self._run_locked("Battle Tests", lambda: validate_battle_fixtures(self.settings.workspace_root))
        if action == "ideBenchContract":
            return self._run_locked("IDE Bench Contract", build_ide_bench_contract)
        if action == "v2Mission":
            changed = supplied.get("changed_files") if isinstance(supplied.get("changed_files"), list) else []
            files = normalize_changed_files(self.settings.workspace_root, changed)
            request = {
                "root": str(self.settings.workspace_root),
                "mode": "changed_files" if files else "repository",
                "mission_type": str(supplied.get("mission_type") or "repository_review"),
                "changed_files": files,
                "source": "standalone:v2-mission",
                "execution_permissions": {
                    "read_only": True,
                    "allow_network": False,
                    "allow_shell": False,
                    "allow_write": False,
                    "allow_untrusted_code": False,
                },
            }
            return self._run_locked("V2 Mission", lambda: run_v2_mission(request))
        raise StandaloneServiceError(f"Mission action is not implemented: {action!r}")

    def _run_locked(self, title: str, operation: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        if not self.runtime.review_lock.acquire(blocking=False):
            raise StandaloneServiceBusy("A Sergeant mission is already running.")
        started = time.monotonic()
        try:
            payload = operation()
            if not isinstance(payload, dict):
                raise StandaloneServiceError("Mission operation returned a non-object payload.")
        finally:
            self.runtime.review_lock.release()

        finished = _utc_now()
        verdict = _verdict(payload)
        mission = {
            "schema_version": SERVICE_CONTRACT,
            "mission_id": f"SGT-{uuid.uuid4().hex[:10].upper()}",
            "title": title,
            "finished_at": finished,
            "finishedAt": finished,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
            "summary": {"verdict": verdict},
            "verdict": verdict,
            "findings": _findings(payload),
            "payload": payload,
            "justFinished": True,
        }
        self.runtime.record_mission(mission)
        return {"schema_version": SERVICE_CONTRACT, "mission": mission, "state": self.runtime.snapshot()}

    def handle_webhook(self, event: str, delivery: str, signature: str | None, body: bytes) -> dict[str, Any]:
        secret = self.settings.webhook_secret
        if not secret:
            raise StandaloneServiceError("GitHub webhook intake is not configured.")
        if len(body) > self.settings.max_request_bytes:
            raise StandaloneServiceError("GitHub webhook payload exceeds the configured request limit.")
        if not verify_github_webhook_signature(secret, body, signature):
            raise PermissionError("GitHub webhook signature verification failed.")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise StandaloneServiceError("GitHub webhook payload must be valid UTF-8 JSON.") from error
        if not isinstance(payload, dict):
            raise StandaloneServiceError("GitHub webhook payload must be a JSON object.")
        normalized = normalize_github_webhook(event, payload, delivery)
        if not self.runtime.remember_delivery(delivery):
            return {
                "schema_version": SERVICE_CONTRACT,
                "accepted": False,
                "duplicate": True,
                "delivery": delivery,
                "reason": "GitHub webhook delivery was already processed.",
            }
        return normalized


class StandaloneHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler], application: StandaloneApplication) -> None:
        self.application = application
        super().__init__(address, handler)


def _handler_type(application: StandaloneApplication) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "SergeantStandalone/1"
        sys_version = ""

        @property
        def app(self) -> StandaloneApplication:
            return application

        def log_message(self, format_string: str, *args: object) -> None:
            print(f"[{_utc_now()}] {self.client_address[0]} {redact_secrets(format_string % args)}", flush=True)

        def _security_headers(self) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; "
                "base-uri 'none'; form-action 'none'",
            )

        def _allowed_origin(self) -> str | None:
            origin = str(self.headers.get("Origin") or "").rstrip("/")
            if not origin:
                return None
            same_origin = f"http://{str(self.headers.get('Host') or '')}".rstrip("/")
            return origin if origin == same_origin or origin in self.app.settings.allowed_origins else ""

        def _json(self, status: int | HTTPStatus, payload: Mapping[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            origin = self._allowed_origin()
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self._security_headers()
            self.end_headers()
            self.wfile.write(body)

        def _bytes(self, status: int | HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(int(status))
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self._security_headers()
            self.end_headers()
            self.wfile.write(body)

        def _common_start(self) -> bool:
            self.app.runtime.record_request()
            if not self.app.runtime.rate_allowed(str(self.client_address[0] or "unknown")):
                self._json(HTTPStatus.TOO_MANY_REQUESTS, {"ok": False, "error": "rate_limited"})
                return False
            if self._allowed_origin() == "":
                self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "origin_not_allowed"})
                return False
            return True

        def _authorized(self) -> bool:
            token = self.app.settings.auth_token
            if not token:
                return True
            supplied = str(self.headers.get("Authorization") or "")
            return supplied.startswith("Bearer ") and hmac.compare_digest(token, supplied[7:])

        def _require_auth(self) -> bool:
            if self._authorized():
                return True
            self._json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "authentication_required", "scheme": "Bearer"})
            return False

        def _read_body(self) -> bytes:
            content_type = str(self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                raise StandaloneServiceError("Request Content-Type must be application/json.")
            try:
                length = int(self.headers.get("Content-Length") or "0")
            except ValueError as error:
                raise StandaloneServiceError("Request Content-Length is invalid.") from error
            if length <= 0:
                raise StandaloneServiceError("Request JSON body is required.")
            if length > self.app.settings.max_request_bytes:
                raise OverflowError("Request payload exceeds the configured size limit.")
            body = self.rfile.read(length)
            if len(body) != length:
                raise StandaloneServiceError("Request body ended before Content-Length bytes were received.")
            return body

        @staticmethod
        def _decode_json(body: bytes) -> dict[str, Any]:
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise StandaloneServiceError("Request body must be valid UTF-8 JSON.") from error
            if not isinstance(payload, dict):
                raise StandaloneServiceError("Request JSON body must be an object.")
            return payload

        def do_OPTIONS(self) -> None:
            if not self._common_start():
                return
            origin = self._allowed_origin()
            self.send_response(HTTPStatus.NO_CONTENT)
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Authorization, Content-Type, X-GitHub-Event, X-GitHub-Delivery, X-Hub-Signature-256",
            )
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Max-Age", "600")
            self._security_headers()
            self.end_headers()

        def do_GET(self) -> None:
            if not self._common_start():
                return
            path = urlparse(self.path).path
            if path == "/health":
                self._json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "schema_version": SERVICE_CONTRACT,
                        "service": "Sergeant",
                        "status": "ready",
                        "uptime_seconds": round(time.monotonic() - self.app.runtime.started_monotonic, 3),
                    },
                )
                return
            if path in {"/", "/index.html"}:
                if not self.app.settings.command_center_enabled:
                    self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "command_center_disabled"})
                    return
                try:
                    self._bytes(HTTPStatus.OK, self.app.command_center(), "text/html; charset=utf-8")
                except StandaloneServiceError as error:
                    self._json(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        {"ok": False, "error": "command_center_unavailable", "message": str(error)},
                    )
                return
            if not self._require_auth():
                return
            if path == "/api/v1/capabilities":
                self._json(HTTPStatus.OK, self.app.capabilities())
            elif path == "/api/v1/state":
                self._json(HTTPStatus.OK, self.app.runtime.snapshot())
            elif path == "/api/v1/reports/latest":
                latest = self.app.runtime.last_result
                self._json(HTTPStatus.OK, latest) if latest else self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "no_report"})
            else:
                self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

        def do_POST(self) -> None:
            if not self._common_start():
                return
            path = urlparse(self.path).path
            try:
                body = self._read_body()
                if path == "/api/v1/github/webhook":
                    result = self.app.handle_webhook(
                        str(self.headers.get("X-GitHub-Event") or ""),
                        str(self.headers.get("X-GitHub-Delivery") or ""),
                        self.headers.get("X-Hub-Signature-256"),
                        body,
                    )
                    self._json(HTTPStatus.ACCEPTED if result.get("accepted") else HTTPStatus.OK, result)
                    return
                if not self._require_auth():
                    return
                payload = self._decode_json(body)
                if path == "/api/v1/review":
                    self._json(HTTPStatus.OK, self.app.execute_review(payload))
                elif path == "/api/v1/missions":
                    self._json(HTTPStatus.OK, self.app.execute_mission(payload))
                elif path == "/api/v1/settings":
                    supplied = payload.get("settings") if isinstance(payload.get("settings"), Mapping) else payload
                    settings = self.app.runtime.update_ui_settings(supplied)
                    self._json(HTTPStatus.OK, {"ok": True, "settings": settings, "state": self.app.runtime.snapshot()})
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
            except OverflowError as error:
                self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"ok": False, "error": "request_too_large", "message": str(error)})
            except PermissionError as error:
                self._json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "signature_invalid", "message": str(error)})
            except StandaloneServiceBusy as error:
                self._json(HTTPStatus.CONFLICT, {"ok": False, "error": "mission_already_running", "message": str(error)})
            except (StandaloneServiceError, HardeningError, TypeError, ValueError) as error:
                self._json(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    {"ok": False, "error": "invalid_request", "message": redact_secrets(error)},
                )
            except Exception as error:  # pragma: no cover - defensive transport boundary
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": "internal_error", "message": redact_secrets(error)},
                )

    return Handler


def create_server(settings: StandaloneSettings, *, review_handler: ReviewHandler = handle_app_review_request) -> StandaloneHTTPServer:
    application = StandaloneApplication(settings, review_handler=review_handler)
    return StandaloneHTTPServer((settings.host, settings.port), _handler_type(application), application)


def serve_forever(settings: StandaloneSettings) -> None:
    server = create_server(settings)
    host, port = server.server_address[:2]
    print(
        json.dumps(
            {
                "schema_version": SERVICE_CONTRACT,
                "service": "Sergeant",
                "status": "ready",
                "url": f"http://{host}:{port}",
                "workspace": str(settings.workspace_root),
                "authentication": "bearer-token" if settings.auth_token else "loopback-trust",
                "webhook_intake": bool(settings.webhook_secret),
                "repository_write": False,
                "github_write": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sergeant-serve", description="Run Sergeant as a self-hosted review service.")
    parser.add_argument("--workspace", default=".", help="Repository workspace Sergeant may review.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind host. Non-loopback hosts require an auth token.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--token-env", default="SERGEANT_SERVICE_TOKEN", help="Environment variable containing the bearer token.")
    parser.add_argument(
        "--webhook-secret-env",
        default="SERGEANT_WEBHOOK_SECRET",
        help="Environment variable containing the GitHub webhook secret.",
    )
    parser.add_argument("--allow-origin", action="append", default=[], help="Additional exact browser origin permitted by CORS.")
    parser.add_argument("--max-request-bytes", type=int, default=DEFAULT_MAX_REQUEST_BYTES)
    parser.add_argument("--rate-limit", type=int, default=DEFAULT_RATE_LIMIT, help="Requests per client IP per minute.")
    parser.add_argument("--no-command-center", action="store_true")
    parser.add_argument("--check", action="store_true", help="Validate configuration and package resources without binding a port.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = StandaloneSettings.build(
        args.workspace,
        host=args.host,
        port=args.port,
        auth_token_env=args.token_env,
        webhook_secret_env=args.webhook_secret_env,
        allowed_origins=args.allow_origin,
        max_request_bytes=args.max_request_bytes,
        rate_limit_per_minute=args.rate_limit,
        command_center_enabled=not args.no_command_center,
    )
    if args.check:
        application = StandaloneApplication(settings)
        if settings.command_center_enabled:
            application.command_center()
        print(
            json.dumps(
                {"ok": True, "configuration": settings.public_dict(), "capabilities": application.capabilities()},
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    serve_forever(settings)
    return 0


__all__ = [
    "SERVICE_CONTRACT",
    "StandaloneApplication",
    "StandaloneHTTPServer",
    "StandaloneRuntime",
    "StandaloneServiceBusy",
    "StandaloneServiceError",
    "StandaloneSettings",
    "build_command_center_document",
    "build_parser",
    "create_server",
    "main",
    "normalize_github_webhook",
    "serve_forever",
    "verify_github_webhook_signature",
]
