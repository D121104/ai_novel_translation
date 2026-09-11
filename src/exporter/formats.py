import io
import json
import posixpath
import zipfile
from dataclasses import asdict, dataclass
from html import escape
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

_IGNORED_TAGS = {"script", "style", "head"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


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
    source_epub: bytes | None = None


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
    payload.pop("source_epub", None)
    payload["chapters"] = [
        asdict(chapter) for chapter in sorted(novel.chapters, key=lambda item: item.index)
    ]
    if not bilingual:
        for chapter in payload["chapters"]:
            chapter.pop("source_text", None)
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def export_epub(novel: ExportNovel, *, bilingual: bool = False) -> bytes:
    if novel.source_epub is not None and zipfile.is_zipfile(io.BytesIO(novel.source_epub)):
        return _export_source_epub(novel, bilingual=bilingual)

    return _export_generated_epub(novel, bilingual=bilingual)


def _export_generated_epub(novel: ExportNovel, *, bilingual: bool = False) -> bytes:
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


@dataclass(frozen=True)
class _SourceDocument:
    path: str
    data: bytes
    visible_text: str


class _VisibleTextExtractor(HTMLParser):
    def __init__(self, *, skip_headings: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_headings = skip_headings
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in _IGNORED_TAGS or self._skip_headings and tag.lower() in _HEADING_TAGS:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if (
            tag.lower() in _IGNORED_TAGS or self._skip_headings and tag.lower() in _HEADING_TAGS
        ) and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0 and data.strip():
            self.parts.append(data.strip())


class _VisibleTextRewriter(HTMLParser):
    def __init__(self, replacements: tuple[str, ...], *, skip_headings: bool = True) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_headings = skip_headings
        self._replacements = replacements
        self._replacement_index = 0
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(self.get_starttag_text() or f"<{tag}>")
        if tag.lower() in _IGNORED_TAGS or self._skip_headings and tag.lower() in _HEADING_TAGS:
            self._ignored_depth += 1

    def handle_startendtag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(self.get_starttag_text() or f"<{tag} />")

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")
        if (
            tag.lower() in _IGNORED_TAGS or self._skip_headings and tag.lower() in _HEADING_TAGS
        ) and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth or not data.strip():
            self.parts.append(data)
            return
        replacement = self._replacements[self._replacement_index]
        self._replacement_index += 1
        leading = data[: len(data) - len(data.lstrip())]
        trailing = data[len(data.rstrip()) :]
        self.parts.append(f"{leading}{escape(replacement, quote=False)}{trailing}")

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.parts.append(f"<?{data}>")


def _visible_text(data: bytes) -> str:
    parser = _VisibleTextExtractor()
    parser.feed(data.decode("utf-8", errors="replace"))
    return "\n".join(parser.parts)


def _source_epub_documents(archive: zipfile.ZipFile) -> tuple[_SourceDocument, ...]:
    names = set(archive.namelist())
    container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
    rootfile = next(
        element.attrib["full-path"]
        for element in container.iter()
        if element.tag.endswith("rootfile")
    )
    opf = ElementTree.fromstring(archive.read(rootfile))
    base = posixpath.dirname(rootfile)
    manifest: dict[str, tuple[str, str, str]] = {}
    for item in opf.iter():
        if not item.tag.endswith("item"):
            continue
        item_id = item.attrib.get("id")
        href = item.attrib.get("href")
        if item_id and href:
            manifest[item_id] = (
                posixpath.normpath(posixpath.join(base, unquote(urlsplit(href).path))),
                item.attrib.get("media-type", ""),
                item.attrib.get("properties", ""),
            )

    documents: list[_SourceDocument] = []
    for itemref in opf.iter():
        if not itemref.tag.endswith("itemref"):
            continue
        manifest_item = manifest.get(itemref.attrib.get("idref", ""))
        if manifest_item is None or "nav" in manifest_item[2].split():
            continue
        path, media_type, _properties = manifest_item
        if media_type not in {"application/xhtml+xml", "text/html"} or path not in names:
            continue
        data = archive.read(path)
        documents.append(_SourceDocument(path, data, _visible_text(data)))
    return tuple(documents)


def _normalized_text(text: str) -> str:
    return " ".join(text.split())


def _chapter_document_indices(
    documents: tuple[_SourceDocument, ...], chapters: tuple[ExportChapter, ...]
) -> dict[int, tuple[int, ...]]:
    available = set(range(len(documents)))
    matches: dict[int, tuple[int, ...]] = {}
    for chapter in sorted(chapters, key=lambda item: item.index):
        source = _normalized_text(chapter.source_text)
        fragments = [
            fragment
            for fragment in (_normalized_text(line) for line in chapter.source_text.splitlines())
            if len(fragment) >= 8
        ]
        candidates = [
            index
            for index in sorted(available)
            if source
            and (
                source in _normalized_text(documents[index].visible_text)
                or any(
                    fragment in _normalized_text(documents[index].visible_text)
                    for fragment in fragments
                )
            )
        ]
        match = min(candidates, default=None)
        if match is None and available:
            match = min(available)
        if match is not None:
            chapter_documents = [match]
            available.discard(match)
            for candidate in candidates:
                if candidate == match or candidate not in available:
                    continue
                if candidate != chapter_documents[-1] + 1:
                    break
                chapter_documents.append(candidate)
                available.discard(candidate)
            matches[chapter.index] = tuple(chapter_documents)
    return matches


def _split_replacement(text: str, count: int) -> tuple[str, ...]:
    if count == 0:
        return ()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return (text,) + ("",) * (count - 1)
    if len(lines) <= count:
        return tuple(lines + [""] * (count - len(lines)))
    quotient, remainder = divmod(len(lines), count)
    result: list[str] = []
    cursor = 0
    for index in range(count):
        size = quotient + (1 if index < remainder else 0)
        result.append("\n".join(lines[cursor : cursor + size]))
        cursor += size
    return tuple(result)


def _rewrite_document(data: bytes, translated_text: str, *, bilingual: bool) -> bytes:
    extractor = _VisibleTextExtractor(skip_headings=True)
    decoded = data.decode("utf-8", errors="replace")
    extractor.feed(decoded)
    body_text_count = len(extractor.parts)
    if body_text_count == 0:
        return data
    replacement = translated_text
    if bilingual:
        replacement = f"[SOURCE]\n{_visible_text(data)}\n\n[TRANSLATION]\n{translated_text}"
    rewriter = _VisibleTextRewriter(_split_replacement(replacement, body_text_count))
    rewriter.feed(decoded)
    return "".join(rewriter.parts).encode("utf-8")


def _body_text_count(data: bytes) -> int:
    extractor = _VisibleTextExtractor(skip_headings=True)
    extractor.feed(data.decode("utf-8", errors="replace"))
    return len(extractor.parts)


def _export_source_epub(novel: ExportNovel, *, bilingual: bool = False) -> bytes:
    source = io.BytesIO(novel.source_epub or b"")
    output = io.BytesIO()
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(output, "w") as archive:
        documents = _source_epub_documents(original)
        matches = _chapter_document_indices(documents, tuple(novel.chapters))
        rewritten: dict[str, bytes] = {}
        chapters_by_index = {chapter.index: chapter for chapter in novel.chapters}
        for chapter_index, document_indices in matches.items():
            chapter = chapters_by_index[chapter_index]
            if chapter.translated_text:
                document_counts = [
                    _body_text_count(documents[document_index].data)
                    for document_index in document_indices
                ]
                total_count = sum(document_counts)
                if total_count:
                    replacement = chapter.translated_text
                    if bilingual:
                        replacement = (
                            f"[SOURCE]\n{_visible_text(documents[document_indices[0]].data)}\n\n"
                            f"[TRANSLATION]\n{chapter.translated_text}"
                        )
                    replacements = _split_replacement(replacement, total_count)
                    cursor = 0
                    for document_index, count in zip(
                        document_indices, document_counts, strict=True
                    ):
                        document = documents[document_index]
                        rewritten[document.path] = _rewrite_document(
                            document.data,
                            "\n".join(replacements[cursor : cursor + count]),
                            bilingual=False,
                        )
                        cursor += count

        infos = original.infolist()
        mimetype_info = next((info for info in infos if info.filename == "mimetype"), None)
        if mimetype_info is not None:
            mimetype_info.compress_type = zipfile.ZIP_STORED
            archive.writestr(mimetype_info, original.read("mimetype"))
        for info in infos:
            if info.filename == "mimetype":
                continue
            archive.writestr(info, rewritten.get(info.filename, original.read(info.filename)))
    return output.getvalue()


def _paragraphs(text: str) -> str:
    return "".join(
        f"<p>{escape(paragraph)}</p>" for paragraph in text.splitlines() if paragraph.strip()
    )
