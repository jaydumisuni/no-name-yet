"""Production-safe wrapper around the Sergeant V2 mission builder."""
from __future__ import annotations

from typing import Any

from .review_contract import normalize_review_request
from .v2_mission import run_v2_mission as _run_v2_mission


def run_v2_mission(request: dict[str, Any], *, evidence_consensus: dict[str, Any] | None = None) -> dict[str, Any]:
    """Normalize permissions and paths before invoking the V2 mission builder."""

    normalized = normalize_review_request(request)
    return _run_v2_mission(normalized, evidence_consensus=evidence_consensus)
