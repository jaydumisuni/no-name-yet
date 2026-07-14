"""Compatibility entrypoint for Sergeant's self-hosted service."""
from __future__ import annotations

from .service import (
    SERVICE_CONTRACT,
    StandaloneApplication,
    StandaloneHTTPServer,
    StandaloneRuntime,
    StandaloneServiceBusy,
    StandaloneServiceError,
    StandaloneSettings,
    build_command_center_document,
    build_parser,
    create_server,
    main,
    normalize_github_webhook,
    serve_forever,
    verify_github_webhook_signature,
)

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


if __name__ == "__main__":
    raise SystemExit(main())
