from __future__ import annotations

import json
from pathlib import Path


def test_transfer_32_lane_pool_is_unique_and_well_formed() -> None:
    lanes_path = Path(".github/transfer-lanes/transfer-32.json")
    lanes = json.loads(lanes_path.read_text(encoding="utf-8"))

    assert [lane["lane"] for lane in lanes] == ["ocaml", "julia", "crystal"]

    all_repositories: list[str] = []
    for lane in lanes:
        repositories = lane["repos"]
        assert repositories
        assert len(repositories) == len(set(repositories))
        assert all("/" in repository for repository in repositories)
        assert lane["suffixes"]
        all_repositories.extend(repositories)

    assert len(all_repositories) == len(set(all_repositories))


def test_transfer_32_workflow_freezes_campaign_reviewer_and_truth_boundary() -> None:
    workflow = Path(
        ".github/workflows/model-free-core-transfer-32.yml"
    ).read_text(encoding="utf-8")

    assert "REVIEWER_SHA: 46f949ac72d532068d599e55a3790af5de4da483" in workflow
    assert "SET_ID: model-free-core-transfer-32" in workflow
    assert "SERGEANT_LLM_ENABLED: \"false\"" in workflow
    assert "SERGEANT_CPL_ENABLED: \"false\"" in workflow
    assert "expected_defects_visible_to_sergeant\": False" in workflow
    assert "test ! -e main_review/static_transfer_32_review.py" in workflow
