from __future__ import annotations

import pytest

from scripts import select_opaque_transfer_candidates as selector


def _page(path: str) -> int:
    marker = "&page="
    assert marker in path
    return int(path.rsplit(marker, 1)[1])


def test_pr_files_collects_every_changed_file_page(monkeypatch) -> None:
    calls: list[str] = []

    def fake_api(path: str, headers: dict[str, str]):
        calls.append(path)
        page = _page(path)
        if page == 1:
            return [{"filename": f"src/file-{index}.py"} for index in range(100)]
        if page == 2:
            return [
                {"filename": "tests/test_late.py"},
                {"filename": "src/late.py"},
            ]
        raise AssertionError(f"unexpected page {page}")

    monkeypatch.setattr(selector, "_api", fake_api)

    rows = selector._pr_files("example/project", 77, {"Accept": "json"})

    assert len(rows) == 102
    assert rows[-2]["filename"] == "tests/test_late.py"
    assert rows[-1]["filename"] == "src/late.py"
    assert calls == [
        "/repos/example/project/pulls/77/files?per_page=100&page=1",
        "/repos/example/project/pulls/77/files?per_page=100&page=2",
    ]


def test_exact_full_page_requires_followup_page(monkeypatch) -> None:
    def fake_api(path: str, headers: dict[str, str]):
        if _page(path) == 1:
            return [{"filename": f"src/file-{index}.py"} for index in range(100)]
        return []

    monkeypatch.setattr(selector, "_api", fake_api)

    rows = selector._pr_files("example/project", 78, {})

    assert len(rows) == 100


def test_non_list_file_page_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(selector, "_api", lambda path, headers: {"message": "unexpected"})

    with pytest.raises(selector.IncompletePullRequestFileList, match="non-list"):
        selector._pr_files("example/project", 79, {})


def test_malformed_row_inside_file_page_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        selector,
        "_api",
        lambda path, headers: [{"filename": "src/valid.py"}, "invalid"],
    )

    with pytest.raises(selector.IncompletePullRequestFileList, match="malformed PR file rows"):
        selector._pr_files("example/project", 80, {})


def test_github_three_thousand_file_boundary_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        selector,
        "_api",
        lambda path, headers: [
            {"filename": f"src/page-{_page(path)}-file-{index}.py"}
            for index in range(100)
        ],
    )

    with pytest.raises(selector.IncompletePullRequestFileList, match="3000-file boundary"):
        selector._pr_files("example/project", 81, {})
