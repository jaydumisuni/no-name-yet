from __future__ import annotations

import json
from pathlib import Path


def test_transfer_34_lane_pool_is_unique_and_well_formed() -> None:
    lanes_path = Path(".github/transfer-lanes/transfer-34.json")
    lanes = json.loads(lanes_path.read_text(encoding="utf-8"))

    assert [lane["lane"] for lane in lanes] == ["cpp", "java", "python"]

    all_repositories: list[str] = []
    for lane in lanes:
        repositories = lane["repos"]
        assert repositories
        assert len(repositories) == len(set(repositories))
        assert all("/" in repository for repository in repositories)
        assert lane["suffixes"]
        all_repositories.extend(repositories)

    assert len(all_repositories) == len(set(all_repositories))


def test_transfer_34_workflow_freezes_campaign_reviewer_and_truth_boundary() -> None:
    workflow = Path(
        ".github/workflows/model-free-core-transfer-34.yml"
    ).read_text(encoding="utf-8")

    assert "REVIEWER_SHA: 8b5c1f3f4b62e802526f350e1c28d5c9172d59a8" in workflow
    assert "SET_ID: model-free-core-transfer-34" in workflow
    assert "SERGEANT_LLM_ENABLED: \"false\"" in workflow
    assert "SERGEANT_CPL_ENABLED: \"false\"" in workflow
    assert "expected_defects_visible_to_sergeant\": False" in workflow
    assert "test ! -e main_review/static_transfer_32_review.py" in workflow
    assert "test ! -e main_review/static_transfer_33_review.py" in workflow
    assert "test ! -e main_review/static_transfer_34_review.py" in workflow
