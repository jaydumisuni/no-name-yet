from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_model_routes_and_usage_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Keep unit tests off live routes and away from the user's usage ledger."""

    monkeypatch.setenv("SERGEANT_LLM_ENABLED", "false")
    monkeypatch.setenv(
        "SERGEANT_CLOUDFLARE_USAGE_STATE",
        str(tmp_path / "cloudflare-usage.json"),
    )
