import io
import json
import zipfile

import pytest

from src.ingestion.parser import detect_chapters, normalize_text, parse_bytes
from src.ingestion.service import ImportService


def test_text_normalization_and_chapter_order() -> None:
    chapters = detect_chapters("Chương 2\nsecond\n\nChapter 3\nthird")
    assert [chapter.index for chapter in chapters] == [1, 2]
    assert chapters[0].title == "Chương 2"
    assert chapters[1].text == "third"
    assert normalize_text(b"a\r\nb") == "a\nb"


def test_chinese_chapter_headings_are_detected() -> None:
    chapters = detect_chapters("第一章 开始\nfirst\n\n第2章 继续\nsecond")
    assert [chapter.title for chapter in chapters] == ["第一章 开始", "第2章 继续"]
    assert [chapter.text for chapter in chapters] == ["first", "second"]


def test_epub_without_headings_uses_xhtml_files_as_chapters() -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("chapter-2.xhtml", "<p>Second chapter</p>")
        archive.writestr("chapter-1.xhtml", "<p>First chapter</p>")

    novel = parse_bytes("book.epub", stream.getvalue())
    assert [chapter.text for chapter in novel.chapters] == ["First chapter", "Second chapter"]


def test_epub_uses_opf_spine_and_navigation_titles() -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            '<container><rootfiles><rootfile full-path="OPS/content.opf"/></rootfiles></container>',
        )
        archive.writestr(
            "OPS/content.opf",
            "<package><manifest>"
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
            '<item id="two" href="two.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="one" href="one.xhtml" media-type="application/xhtml+xml"/>'
            '</manifest><spine><itemref idref="one"/><itemref idref="two"/></spine></package>',
        )
        archive.writestr(
            "OPS/nav.xhtml",
            '<nav><ol><li><a href="one.xhtml">第一章 开始</a></li>'
            '<li><a href="two.xhtml">第二章 继续</a></li></ol></nav>',
        )
        archive.writestr("OPS/one.xhtml", "<p>One</p>")
        archive.writestr("OPS/two.xhtml", "<p>Two</p>")

    novel = parse_bytes("book.epub", stream.getvalue())
    assert [chapter.title for chapter in novel.chapters] == ["第一章 开始", "第二章 继续"]
    assert [chapter.text for chapter in novel.chapters] == ["One", "Two"]


def test_epub_merges_adjacent_duplicate_chapter_fragments() -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            '<container><rootfiles><rootfile full-path="content.opf"/></rootfiles></container>',
        )
        archive.writestr(
            "content.opf",
            "<package><manifest>"
            '<item id="one" href="one.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="one-part" href="one-part.xhtml" media-type="application/xhtml+xml"/>'
            '</manifest><spine><itemref idref="one"/><itemref idref="one-part"/></spine></package>',
        )
        archive.writestr("one.xhtml", "<h1>第15章 红缨辔</h1><p>Beginning.</p>")
        archive.writestr("one-part.xhtml", "<h1>第15章</h1><p>Continuation.</p>")

    novel = parse_bytes("book.epub", stream.getvalue())
    assert len(novel.chapters) == 1
    assert novel.chapters[0].title == "第15章 红缨辔"
    assert "Beginning." in novel.chapters[0].text
    assert "Continuation." in novel.chapters[0].text


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
