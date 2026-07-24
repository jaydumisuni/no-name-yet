from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "52-open-pr-closure-and-branch-retirement.md"


def test_retirement_manifest_accounts_for_every_closed_historical_pr() -> None:
    text = MANIFEST.read_text(encoding="utf-8")
    expected = {
        47,
        65,
        96,
        97,
        104,
        105,
        106,
        113,
        114,
        115,
        116,
        117,
        118,
        124,
        125,
        126,
        127,
        128,
        132,
        133,
        141,
    }
    for number in expected:
        assert f"#{number}" in text


def test_retirement_manifest_preserves_recovery_and_future_salvage_boundaries() -> None:
    text = MANIFEST.read_text(encoding="utf-8")

    assert "Keep `main` as the only permanent branch" in text
    assert "future 0.5.0 release branch must be cut from the current `main`" in text
    assert "future design reference for model-council adjudication" in text
    assert "GitHub pull-request pages remain the permanent reference" in text
    assert "32b50050779751f825b15e25a2af518e5e3b27af" in text
