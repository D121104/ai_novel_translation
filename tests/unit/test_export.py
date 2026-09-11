import json
import zipfile
from io import BytesIO

from src.exporter.formats import ExportChapter, ExportNovel, export_epub, export_json, export_txt


def novel() -> ExportNovel:
    return ExportNovel(
        "Book",
        "Author",
        "en",
        "vi",
        (ExportChapter(2, "Two", "B", "BB"), ExportChapter(1, "One", "A", "AA")),
    )


def test_exports_preserve_order_and_bilingual_content() -> None:
    item = novel()
    assert export_txt(item, bilingual=True).decode().index("One") < export_txt(
        item, bilingual=True
    ).decode().index("Two")
    payload = json.loads(export_json(item))
    assert [chapter["title"] for chapter in payload["chapters"]] == ["One", "Two"]


def test_epub_is_readable_and_ordered() -> None:
    with zipfile.ZipFile(BytesIO(export_epub(novel()))) as archive:
        assert archive.read("mimetype") == b"application/epub+zip"
        assert archive.namelist().index("OEBPS/c1.xhtml") < archive.namelist().index(
            "OEBPS/c2.xhtml"
        )


def test_epub_contains_navigation_metadata_and_full_chapter_translation() -> None:
    item = ExportNovel(
        "Novel & More",
        "Author",
        "en",
        "vi",
        (ExportChapter(1, "One", "Source one", "Translation one\n\nTranslation two"),),
    )

    with zipfile.ZipFile(BytesIO(export_epub(item))) as archive:
        assert archive.read("OEBPS/nav.xhtml")
        opf = archive.read("OEBPS/content.opf").decode()
        chapter = archive.read("OEBPS/c1.xhtml").decode()
        assert 'version="3.0"' in opf
        assert "Novel &amp; More" in opf
        assert "Translation one" in chapter
        assert "Translation two" in chapter
