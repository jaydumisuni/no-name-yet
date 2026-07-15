"""Loopback-only Cloudflare Workers AI gateway for Sergeant.

The gateway keeps a user's Cloudflare credentials on their own machine while
presenting a small OpenAI-compatible surface to Sergeant:

- ``GET /health``
- ``GET /v1/models``
- ``POST /v1/chat/completions``

It is intentionally not a general proxy. Model IDs must come from the configured
roster, the upstream host is fixed to Cloudflare, request sizes are bounded, and
network binding is always loopback-only in this release.
"""
from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from typing import Any, Iterable

from .cloudflare_models import (
    CLOUDFLARE_FREE_BALANCED_MODELS,
    CLOUDFLARE_PROVIDER,
    configured_model_roster,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8082
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_REQUEST_BYTES = 1_500_000
DEFAULT_MODELS = CLOUDFLARE_FREE_BALANCED_MODELS
ACCOUNT_ID_RE = __import__("re").compile(r"^[A-Fa-f0-9]{32}$")


class CloudflareGatewayError(RuntimeError):
    """Raised when Cloudflare gateway configuration or transport fails."""


class CloudflareGatewayRequestError(CloudflareGatewayError):
    """Raised when a local client submits an invalid gateway request."""


def _csv(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.strip() for item in value.split(",") if item.strip()))


def _bounded_float(name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return min(high, max(low, value))


def _bounded_int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return min(high, max(low, value))


def is_loopback_host(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized in {"localhost", "ip6-localhost"}:
        return True
    try:
        return ip_address(normalized).is_loopback
    except ValueError:
        try:
            addresses = socket.getaddrinfo(host, None)
            return bool(addresses) and all(ip_address(item[4][0]).is_loopback for item in addresses)
        except (OSError, ValueError):
            return False


@dataclass(frozen=True)
class CloudflareGatewaySettings:
    account_id: str
    api_token: str
    models: tuple[str, ...]
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES

    @classmethod
    def from_environment(
        cls,
        *,
        host: str | None = None,
        port: int | None = None,
    ) -> "CloudflareGatewaySettings":
        account_id = os.getenv("SERGEANT_CLOUDFLARE_ACCOUNT_ID", os.getenv("CLOUDFLARE_ACCOUNT_ID", "")).strip()
        api_token = os.getenv("SERGEANT_CLOUDFLARE_API_TOKEN", os.getenv("CLOUDFLARE_API_TOKEN", "")).strip()
        explicit_models = os.getenv("SERGEANT_CLOUDFLARE_MODELS", "")
        models = configured_model_roster(CLOUDFLARE_PROVIDER, explicit_models)
        return cls(
            account_id=account_id,
            api_token=api_token,
            models=models,
            host=(host or os.getenv("SERGEANT_CLOUDFLARE_HOST", DEFAULT_HOST)).strip(),
            port=port or _bounded_int("SERGEANT_CLOUDFLARE_PORT", DEFAULT_PORT, 1, 65535),
            timeout_seconds=_bounded_float("SERGEANT_CLOUDFLARE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS, 2.0, 900.0),
            max_request_bytes=_bounded_int(
                "SERGEANT_CLOUDFLARE_MAX_REQUEST_BYTES",
                DEFAULT_MAX_REQUEST_BYTES,
                16_384,
                8_000_000,
            ),
        )

    @property
    def upstream_chat_url(self) -> str:
        return f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/v1/chat/completions"

    def validate(self, *, require_credentials: bool = True) -> None:
        if require_credentials and not self.account_id:
            raise CloudflareGatewayError("Cloudflare Account ID is missing.")
        if self.account_id and not ACCOUNT_ID_RE.fullmatch(self.account_id):
            raise CloudflareGatewayError("Cloudflare Account ID must be a 32-character hexadecimal value.")
        if require_credentials and not self.api_token:
            raise CloudflareGatewayError("Cloudflare API token is missing.")
        if not self.models:
            raise CloudflareGatewayError("At least one Cloudflare model must be configured.")
        if any(not model.startswith("@cf/") for model in self.models):
            raise CloudflareGatewayError("Cloudflare model IDs must begin with '@cf/'.")
        if not is_loopback_host(self.host):
            raise CloudflareGatewayError("Cloudflare gateway is loopback-only in this release.")

    def public_dict(self) -> dict[str, Any]:
        return {
            "provider": "cloudflare-workers-ai",
            "configured": bool(self.account_id and self.api_token),
            "account_id_present": bool(self.account_id),
            "api_token_present": bool(self.api_token),
            "models": list(self.models),
            "host": self.host,
            "port": self.port,
            "base_url": f"http://{self.host}:{self.port}/v1",
            "loopback_only": True,
            "timeout_seconds": self.timeout_seconds,
            "max_request_bytes": self.max_request_bytes,
        }


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _validate_chat_payload(settings: CloudflareGatewaySettings, payload: dict[str, Any]) -> None:
    model = str(payload.get("model") or "").strip()
    if model not in settings.models:
        raise CloudflareGatewayRequestError(f"Model is not in the configured Cloudflare roster: {model!r}")
    if payload.get("stream") is True:
        raise CloudflareGatewayRequestError("Streaming is not enabled in the first Cloudflare gateway release.")
    if not isinstance(payload.get("messages"), list) or not payload["messages"]:
        raise CloudflareGatewayRequestError("A non-empty OpenAI-compatible messages array is required.")


def _cloudflare_request(settings: CloudflareGatewaySettings, payload: dict[str, Any]) -> tuple[int, bytes]:
    _validate_chat_payload(settings, payload)
    request = urllib.request.Request(
        settings.upstream_chat_url,
        data=_json_bytes(payload),
        headers={
            "Authorization": f"Bearer {settings.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "sergeant-reviewer/cloudflare-gateway",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.timeout_seconds) as response:
            return int(getattr(response, "status", 200)), response.read()
    except urllib.error.HTTPError as error:
        return int(error.code), error.read()
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as error:
        raise CloudflareGatewayError(f"Cloudflare Workers AI is unavailable: {error}") from error


def make_handler(settings: CloudflareGatewaySettings) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "SergeantCloudflareGateway/1"

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            if os.getenv("SERGEANT_CLOUDFLARE_LOG_REQUESTS", "false").strip().lower() in {"1", "true", "yes"}:
                super().log_message(format, *args)

        def _send(self, status: int, payload: object) -> None:
            body = payload if isinstance(payload, bytes) else _json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._send(200, {"status": "ready", **settings.public_dict()})
                return
            if self.path in {"/models", "/v1/models"}:
                self._send(
                    200,
                    {
                        "object": "list",
                        "data": [
                            {"id": model, "object": "model", "owned_by": "cloudflare"}
                            for model in settings.models
                        ],
                    },
                )
                return
            self._send(404, {"error": {"message": "Unsupported gateway path."}})

        def do_POST(self) -> None:  # noqa: N802
            if self.path not in {"/chat/completions", "/v1/chat/completions"}:
                self._send(404, {"error": {"message": "Unsupported gateway path."}})
                return
            raw_length = self.headers.get("Content-Length", "")
            try:
                length = int(raw_length)
            except ValueError:
                self._send(411, {"error": {"message": "A valid Content-Length header is required."}})
                return
            if length < 2 or length > settings.max_request_bytes:
                self._send(413, {"error": {"message": "Request body exceeds the configured gateway limit."}})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send(400, {"error": {"message": "Request body must be a JSON object."}})
                return
            if not isinstance(payload, dict):
                self._send(400, {"error": {"message": "Request body must be a JSON object."}})
                return
            try:
                status, body = _cloudflare_request(settings, payload)
            except CloudflareGatewayRequestError as error:
                self._send(400, {"error": {"message": str(error)}})
                return
            except CloudflareGatewayError as error:
                self._send(502, {"error": {"message": str(error)}})
                return
            self._send(status, body)

    return Handler


def build_server(settings: CloudflareGatewaySettings) -> ThreadingHTTPServer:
    settings.validate()
    return ThreadingHTTPServer((settings.host, settings.port), make_handler(settings))


def run_server(settings: CloudflareGatewaySettings) -> None:
    server = build_server(settings)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def model_roster(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
