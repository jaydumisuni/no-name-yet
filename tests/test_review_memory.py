from __future__ import annotations

from main_review.memory import ReviewMemoryStore, default_memory_path, new_memory_record


def test_memory_store_add_list_and_search(tmp_path) -> None:
    store = ReviewMemoryStore(default_memory_path(tmp_path))
    record = new_memory_record(
        kind="decision",
        title="Keep auth separate",
        summary="Authentication stays outside business logic.",
        reason="Multiple clients need to reuse auth without rewriting business services.",
        status="verified",
        evidence=["Architecture review", "Owner approval"],
        tags=["auth", "architecture", "auth"],
        applies_to=["api", "mobile", "api"],
        confidence=1.4,
    )

    saved = store.add(record)
    assert saved.id.startswith("mem_")
    assert saved.confidence == 1.0
    assert saved.tags == ["architecture", "auth"]
    assert saved.applies_to == ["api", "mobile"]

    all_records = store.list()
    assert len(all_records) == 1
    assert all_records[0].title == "Keep auth separate"

    assert store.list(status="verified")[0].id == saved.id
    assert store.list(kind="decision")[0].id == saved.id
    assert store.list(tag="architecture")[0].id == saved.id
    assert store.search("business services")[0].id == saved.id


def test_memory_store_missing_file_is_empty(tmp_path) -> None:
    store = ReviewMemoryStore(default_memory_path(tmp_path))
    assert store.load() == []
    assert store.search("anything") == []


def test_memory_store_rejects_duplicate_ids(tmp_path) -> None:
    store = ReviewMemoryStore(default_memory_path(tmp_path))
    record = new_memory_record(
        kind="principle",
        title="Evidence over ego",
        summary="Conclusions change when stronger evidence appears.",
        reason="The reviewer expects to be challenged.",
    )

    store.add(record)
    try:
        store.add(record)
    except ValueError as exc:
        assert record.id in str(exc)
    else:
        raise AssertionError("duplicate memory record should fail")
