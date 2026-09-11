import io
import json
import zipfile
from dataclasses import asdict, dataclass
from html import escape


@dataclass(frozen=True)
class ExportChapter:
    index: int
    title: str
    source_text: str
    translated_text: str | None = None


@dataclass(frozen=True)
class ExportNovel:
    title: str
    author: str | None
    source_language: str
    target_language: str
    chapters: tuple[ExportChapter, ...]


def export_txt(novel: ExportNovel, *, bilingual: bool = False) -> bytes:
    sections: list[str] = []
    for chapter in sorted(novel.chapters, key=lambda item: item.index):
        text = chapter.source_text if not chapter.translated_text else chapter.translated_text
        if bilingual and chapter.translated_text:
            text = f"[SOURCE]\n{chapter.source_text}\n\n[TRANSLATION]\n{chapter.translated_text}"
        sections.append(f"{chapter.title}\n\n{text}")
    return "\n\n".join(sections).encode("utf-8")


def export_json(novel: ExportNovel, *, bilingual: bool = False) -> bytes:
    payload = asdict(novel)
    payload["chapters"] = [
        asdict(chapter) for chapter in sorted(novel.chapters, key=lambda item: item.index)
    ]
    if not bilingual:
        for chapter in payload["chapters"]:
            chapter.pop("source_text", None)
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def export_epub(novel: ExportNovel, *, bilingual: bool = False) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        chapters = sorted(novel.chapters, key=lambda item: item.index)
        manifest = "".join(
            f'<item id="c{position}" href="c{position}.xhtml" media-type="application/xhtml+xml"/>'
            for position, _chapter in enumerate(chapters, start=1)
        )
        spine = "".join(
            f'<itemref idref="c{position}"/>' for position, _chapter in enumerate(chapters, start=1)
        )
        nav_links = "".join(
            f'<li><a href="c{position}.xhtml">{escape(chapter.title)}</a></li>'
            for position, chapter in enumerate(chapters, start=1)
        )
        metadata = (
            f"<dc:title>{escape(novel.title)}</dc:title>"
            f"<dc:creator>{escape(novel.author or 'Unknown')}</dc:creator>"
            f"<dc:language>{escape(novel.target_language)}</dc:language>"
            '<dc:identifier id="book-id">novel-translator</dc:identifier>'
        )
        archive.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<package version="3.0" unique-identifier="book-id" '
            'xmlns="http://www.idpf.org/2007/opf" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f"<metadata>{metadata}</metadata>"
            f'<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
            f'properties="nav"/>{manifest}</manifest><spine>{spine}</spine></package>',
        )
        archive.writestr(
            "OEBPS/nav.xhtml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Contents</title></head>'
            f'<body><nav epub:type="toc" id="toc"><h1>Contents</h1><ol>{nav_links}</ol>'
            "</nav></body></html>",
        )
        for position, chapter in enumerate(chapters, start=1):
            body = chapter.source_text if not chapter.translated_text else chapter.translated_text
            if bilingual and chapter.translated_text:
                body = (
                    f"<h2>Source</h2>{_paragraphs(chapter.source_text)}"
                    f"<h2>Translation</h2>{_paragraphs(chapter.translated_text)}"
                )
            archive.writestr(
                f"OEBPS/c{position}.xhtml",
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<html xmlns="http://www.w3.org/1999/xhtml">'
                f"<head><title>{escape(chapter.title)}</title></head>"
                f"<body><h1>{escape(chapter.title)}</h1>"
                f"{_paragraphs(body) if not bilingual or not chapter.translated_text else body}"
                "</body></html>",
            )
    return buffer.getvalue()


def _paragraphs(text: str) -> str:
    return "".join(
        f"<p>{escape(paragraph)}</p>" for paragraph in text.splitlines() if paragraph.strip()
    )
