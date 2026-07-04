from __future__ import annotations

from pathlib import Path

from main_review.diff_review import (
    classify_changed_files,
    parse_changed_files_text,
    review_changed_files,
    review_changed_files_file,
)


def test_parse_changed_files_text_accepts_common_formats() -> None:
    text = 'src/app.py, tests/test_app.py\n["README.md"]\n'

    assert parse_changed_files_text(text) == ["src/app.py", "tests/test_app.py", "README.md"]


def test_classify_changed_files_marks_language_role_and_risk() -> None:
    insights = classify_changed_files(["src/app.py", ".github/workflows/ci.yml"])
    by_path = {item.path: item for item in insights}

    assert by_path["src/app.py"].language == "Python"
    assert by_path["src/app.py"].role == "source"
    assert by_path[".github/workflows/ci.yml"].high_risk is True


def test_diff_review_needs_work_for_source_without_tests() -> None:
    payload = review_changed_files(["src/app.py"])

    assert payload["verdict"]["verdict"] == "NEEDS WORK"
    assert any(finding["category"] == "testing" for finding in payload["evidence"]["findings"])


def test_diff_review_passes_docs_only_change() -> None:
    payload = review_changed_files(["docs/guide.md"])

    assert payload["verdict"]["verdict"] == "PASS"
    assert payload["evidence"]["findings"][0]["severity"] == "note"


def test_diff_review_file_input(tmp_path: Path) -> None:
    file_list = tmp_path / "changed.txt"
    file_list.write_text("src/app.py\ntests/test_app.py\n", encoding="utf-8")

    payload = review_changed_files_file(file_list)

    assert payload["verdict"]["verdict"] == "PASS"
    assert payload["evidence"]["changed_files"]
