from __future__ import annotations

from pathlib import Path

from main_review.semantic_scope import semantic_review_files


def test_explicit_changed_files_are_preserved_without_repository_expansion(tmp_path: Path) -> None:
    assert semantic_review_files(tmp_path, ["src/app.py", "src/app.py", "tests/test_app.py"]) == [
        "src/app.py",
        "tests/test_app.py",
    ]


def test_workspace_scope_is_bounded_and_prioritizes_high_risk_files(tmp_path: Path) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "review.yml").write_text("name: review\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    for index in range(5):
        (tmp_path / "src" / f"module_{index}.py").write_text(f"VALUE = {index}\n", encoding="utf-8")
    (tmp_path / "tests" / "test_app.py").write_text("def test_ok(): assert True\n", encoding="utf-8")

    selected = semantic_review_files(tmp_path, [], limit=3)

    assert selected[0] == ".github/workflows/review.yml"
    assert len(selected) == 3
    assert all(not Path(path).is_absolute() for path in selected)
