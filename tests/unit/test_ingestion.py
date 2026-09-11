import json

import pytest

from src.ingestion.parser import detect_chapters, normalize_text, parse_bytes
from src.ingestion.service import ImportService


def test_text_normalization_and_chapter_order() -> None:
    chapters = detect_chapters("Chương 2\nsecond\n\nChapter 3\nthird")
    assert [chapter.index for chapter in chapters] == [1, 2]
    assert chapters[0].title == "Chương 2"
    assert chapters[1].text == "third"
    assert normalize_text(b"a\r\nb") == "a\nb"


def test_json_parser() -> None:
    data = json.dumps({"title": "Novel", "chapters": [{"title": "One", "text": "Text"}]}).encode()
    novel = parse_bytes("book.json", data)
    assert novel.title == "Novel"
    assert novel.chapters[0].text == "Text"


class FakeRepository:
    def __init__(self) -> None:
        self.ids: dict[str, str] = {}

    async def find_by_source_hash(self, source_hash: str) -> str | None:
        return self.ids.get(source_hash)

    async def save(self, novel, source_hash: str, source_path: str) -> str:
        self.ids[source_hash] = "novel-1"
        return "novel-1"


class FakeStorage:
    async def put(self, key: str, data: bytes, content_type: str) -> str:
        return f"s3://novels/{key}"


@pytest.mark.asyncio
async def test_import_is_idempotent() -> None:
    repository = FakeRepository()
    service = ImportService(repository, FakeStorage())
    first = await service.import_file("book.txt", b"Chapter 1\nHello")
    second = await service.import_file("book.txt", b"Chapter 1\nHello")
    assert first.idempotent is False
    assert second.idempotent is True
    assert second.novel_id == first.novel_id
