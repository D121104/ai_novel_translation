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
            '<?xml version="1.0"?><container><rootfiles>'
            '<rootfile full-path="OEBPS/content.opf"/></rootfiles></container>',
        )
        chapters = sorted(novel.chapters, key=lambda item: item.index)
        manifest = "".join(
            f'<item id="c{chapter.index}" href="c{chapter.index}.xhtml" '
            'media-type="application/xhtml+xml"/>'
            for chapter in chapters
        )
        spine = "".join(f'<itemref idref="c{chapter.index}"/>' for chapter in chapters)
        archive.writestr(
            "OEBPS/content.opf",
            f"<package><metadata><dc:title>{escape(novel.title)}</dc:title></metadata><manifest>{manifest}</manifest><spine>{spine}</spine></package>",
        )
        for chapter in chapters:
            body = chapter.source_text if not chapter.translated_text else chapter.translated_text
            if bilingual and chapter.translated_text:
                body = (
                    f"<h2>Source</h2><p>{escape(chapter.source_text)}</p>"
                    f"<h2>Translation</h2><p>{escape(chapter.translated_text)}</p>"
                )
            archive.writestr(
                f"OEBPS/c{chapter.index}.xhtml",
                f"<html><head><title>{escape(chapter.title)}</title></head><body><h1>{escape(chapter.title)}</h1><p>{escape(body)}</p></body></html>",
            )
    return buffer.getvalue()
