from __future__ import annotations

from pathlib import Path

from main_review.static_transfer_17_review import run_static_transfer_17_review


ROOT = "derived-collection-built-but-never-published-to-target"


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_populated_collection_must_be_published_to_model(tmp_path: Path) -> None:
    source = tmp_path / "Mapper.kt"
    source.write_text(
        '''
fun textMedia(model: Comment, text: String) {
    val medias = mutableListOf<Media>()
    for (image in parse(text).images) {
        medias.add(Media(image.url))
    }
}
''',
        encoding="utf-8",
    )

    result = run_static_transfer_17_review(tmp_path, ["Mapper.kt"])

    assert ROOT in _roots(result)


def test_accumulation_into_existing_model_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "Mapper.kt"
    source.write_text(
        '''
fun textMedia(model: Comment, text: String) {
    val medias = mutableListOf<Media>()
    for (image in parse(text).images) {
        medias.add(Media(image.url))
    }
    model.medias = model.medias.plus(medias)
}
''',
        encoding="utf-8",
    )

    result = run_static_transfer_17_review(tmp_path, ["Mapper.kt"])

    assert ROOT not in _roots(result)


def test_collection_returned_to_caller_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "Mapper.kt"
    source.write_text(
        '''
fun photos(model: Comment, source: Photos): List<Media> {
    val medias = mutableListOf<Media>()
    for (photo in source.items) {
        medias.add(Media(photo.url))
    }
    return medias
}
''',
        encoding="utf-8",
    )

    result = run_static_transfer_17_review(tmp_path, ["Mapper.kt"])

    assert ROOT not in _roots(result)
