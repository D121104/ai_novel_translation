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


def test_epub_rewrites_source_text_while_preserving_assets_and_layout() -> None:
    source = BytesIO()
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr(
            "META-INF/container.xml",
            '<container><rootfiles><rootfile full-path="OPS/content.opf"/></rootfiles></container>',
        )
        archive.writestr(
            "OPS/content.opf",
            "<package><manifest>"
            '<item id="style" href="style/book.css" media-type="text/css"/>'
            '<item id="cover" href="images/cover.jpg" media-type="image/jpeg" '
            'properties="cover-image"/>'
            '<item id="image" href="images/scene.png" media-type="image/png"/>'
            '<item id="font" href="fonts/book.woff2" media-type="font/woff2"/>'
            '<item id="chapter" href="text/chapter.xhtml" media-type="application/xhtml+xml"/>'
            '</manifest><spine><itemref idref="chapter"/></spine></package>',
        )
        archive.writestr(
            "OPS/text/chapter.xhtml",
            '<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml">'
            '<head><link rel="stylesheet" href="../style/book.css"/></head>'
            '<body><div class="page" style="position:absolute;left:12px;top:24px">'
            '<p>Source paragraph</p><img src="../images/scene.png" '
            'style="position:absolute;left:30px;top:40px"/></div></body></html>',
        )
        css = b"@font-face{font-family:Book;src:url('../fonts/book.woff2')}"
        archive.writestr("OPS/style/book.css", css)
        archive.writestr("OPS/images/cover.jpg", b"cover-bytes")
        archive.writestr("OPS/images/scene.png", b"scene-bytes")
        archive.writestr("OPS/fonts/book.woff2", b"font-bytes")

    item = ExportNovel(
        "Book",
        "Author",
        "en",
        "vi",
        (ExportChapter(1, "One", "Source paragraph", "Translated paragraph"),),
        source.getvalue(),
    )

    with zipfile.ZipFile(BytesIO(export_epub(item))) as exported:
        assert exported.read("OPS/style/book.css") == (
            b"@font-face{font-family:Book;src:url('../fonts/book.woff2')}"
        )
        assert exported.read("OPS/images/cover.jpg") == b"cover-bytes"
        assert exported.read("OPS/images/scene.png") == b"scene-bytes"
        assert exported.read("OPS/fonts/book.woff2") == b"font-bytes"
        chapter = exported.read("OPS/text/chapter.xhtml").decode()
        assert "Translated paragraph" in chapter
        assert "Source paragraph" not in chapter
        assert "../style/book.css" in chapter
        assert 'style="position:absolute;left:30px;top:40px"' in chapter
        assert "../images/scene.png" in chapter


def test_epub_rewrites_adjacent_fragments_and_keeps_headings() -> None:
    source = BytesIO()
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr(
            "META-INF/container.xml",
            '<container><rootfiles><rootfile full-path="content.opf"/></rootfiles></container>',
        )
        archive.writestr(
            "content.opf",
            "<package><manifest>"
            '<item id="one" href="one.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="two" href="two.xhtml" media-type="application/xhtml+xml"/>'
            '</manifest><spine><itemref idref="one"/><itemref idref="two"/></spine></package>',
        )
        archive.writestr(
            "one.xhtml", "<html><body><h1>Chapter One</h1><p>First fragment text</p></body></html>"
        )
        archive.writestr(
            "two.xhtml", "<html><body><h1>Chapter One</h1><p>Second fragment text</p></body></html>"
        )

    item = ExportNovel(
        "Book",
        "Author",
        "en",
        "vi",
        (
            ExportChapter(
                1,
                "Chapter One",
                "First fragment text\nSecond fragment text",
                "Đoạn thứ nhất\nĐoạn thứ hai",
            ),
        ),
        source.getvalue(),
    )

    with zipfile.ZipFile(BytesIO(export_epub(item))) as exported:
        first = exported.read("one.xhtml").decode()
        second = exported.read("two.xhtml").decode()
        assert "Chapter One" in first and "Đoạn thứ nhất" in first
        assert "Chapter One" in second and "Đoạn thứ hai" in second
        assert "First fragment text" not in first
        assert "Second fragment text" not in second
