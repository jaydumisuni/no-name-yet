from __future__ import annotations

import json
from pathlib import Path


def test_transfer_30_lane_pool_is_unique_and_well_formed() -> None:
    lanes_path = Path(".github/transfer-lanes/transfer-30.json")
    lanes = json.loads(lanes_path.read_text(encoding="utf-8"))

    assert [lane["lane"] for lane in lanes] == ["perl", "fsharp", "nim"]

    all_repositories: list[str] = []
    for lane in lanes:
        repositories = lane["repos"]
        assert repositories
        assert len(repositories) == len(set(repositories))
        assert all("/" in repository for repository in repositories)
        assert lane["suffixes"]
        all_repositories.extend(repositories)

    assert len(all_repositories) == len(set(all_repositories))
    assert "preaction/Yancy" in lanes[0]["repos"]
