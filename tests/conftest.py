from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_live_llm_discovery_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests opt into model routes explicitly instead of probing local services."""

    monkeypatch.setenv("SERGEANT_LLM_ENABLED", "false")
