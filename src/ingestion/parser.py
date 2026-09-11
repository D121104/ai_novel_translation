import io
import json
import posixpath
import re
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree


@dataclass(frozen=True)
class ParsedChapter:
    index: int
    title: str
    text: str


@dataclass(frozen=True)
class ParsedNovel:
    title: str
    author: str | None
    chapters: tuple[ParsedChapter, ...]


def normalize_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return data.decode(encoding).replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


_CHAPTER_RE = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?((?:chapter|chương)\s+[^\n]{1,160}"
    r"|第\s*(?:\d+|[零〇一二两三四五六七八九十百千万]+)\s*(?:章|节|回)[^\n]{0,160})\s*$"
)


def _has_chapter_headings(text: str) -> bool:
    return bool(_CHAPTER_RE.search(text))


def detect_chapters(text: str) -> tuple[ParsedChapter, ...]:
    matches = list(_CHAPTER_RE.finditer(text))
    if not matches:
        return (ParsedChapter(1, "Chapter 1", text.strip()),)
    chapters: list[ParsedChapter] = []
    for index, match in enumerate(matches, start=1):
        end = matches[index].start() if index < len(matches) else len(text)
        title = " ".join(match.group(1).split())
        chapters.append(ParsedChapter(index, title, text[match.end() : end].strip()))
    return tuple(chapters)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return "\n".join(self.parts)


def parse_bytes(filename: str, data: bytes) -> ParsedNovel:
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        payload = json.loads(normalize_text(data))
        chapters = tuple(
            ParsedChapter(i, item.get("title", f"Chapter {i}"), item.get("text", ""))
            for i, item in enumerate(payload.get("chapters", []), 1)
        )
        return ParsedNovel(
            payload.get("title", Path(filename).stem), payload.get("author"), chapters
        )
    if suffix == ".epub":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            documents, titles = _read_epub_chapters(archive)
        detected: list[ParsedChapter] = []
        for document, navigation_title in zip(documents, titles, strict=True):
            if _has_chapter_headings(document):
                detected.extend(
                    ParsedChapter(0, navigation_title or chapter.title, chapter.text)
                    for chapter in detect_chapters(document)
                )
            elif document.strip():
                detected.append(
                    ParsedChapter(
                        0,
                        navigation_title or f"Chapter {len(detected) + 1}",
                        document.strip(),
                    )
                )
        document_list, title_list = _merge_duplicate_epub_chapters(
            [chapter.text for chapter in detected], [chapter.title for chapter in detected]
        )
        chapters = tuple(
            ParsedChapter(index, title or f"Chapter {index}", document)
            for index, (document, title) in enumerate(
                zip(document_list, title_list, strict=True), 1
            )
        )
        return ParsedNovel(
            Path(filename).stem,
            None,
            chapters or (ParsedChapter(1, "Chapter 1", ""),),
        )
    text = normalize_text(data)
    return ParsedNovel(Path(filename).stem, None, detect_chapters(text))


def _extract_html(data: bytes) -> str:
    parser = _TextExtractor()
    parser.feed(normalize_text(data))
    return parser.text()


def _read_epub_chapters(archive: zipfile.ZipFile) -> tuple[list[str], list[str]]:
    """Read EPUB XHTML in OPF spine order, using the navigation title when available."""
    names = set(archive.namelist())
    if "META-INF/container.xml" not in names:
        return _fallback_epub_documents(archive, names)
    container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
    rootfile = next(
        element.attrib["full-path"]
        for element in container.iter()
        if element.tag.endswith("rootfile")
    )
    if rootfile not in names:
        return _fallback_epub_documents(archive, names)
    opf = ElementTree.fromstring(archive.read(rootfile))
    base = posixpath.dirname(rootfile)
    manifest: dict[str, tuple[str, str, str]] = {}
    for manifest_entry in opf.iter():
        if not manifest_entry.tag.endswith("item"):
            continue
        item_id = manifest_entry.attrib.get("id")
        href = manifest_entry.attrib.get("href")
        if item_id and href:
            manifest[item_id] = (
                posixpath.normpath(posixpath.join(base, unquote(urlsplit(href).path))),
                manifest_entry.attrib.get("media-type", ""),
                manifest_entry.attrib.get("properties", ""),
            )
    titles = _epub_navigation_titles(archive, manifest, names)
    chapters: list[str] = []
    chapter_titles: list[str] = []
    for itemref in opf.iter():
        if not itemref.tag.endswith("itemref"):
            continue
        manifest_item = manifest.get(itemref.attrib.get("idref", ""))
        if manifest_item is None or manifest_item[1] not in {"application/xhtml+xml", "text/html"}:
            continue
        path, _media_type, properties = manifest_item
        if "nav" in properties.split() or path not in names:
            continue
        raw = archive.read(path)
        chapters.append(_extract_html(raw))
        chapter_titles.append(titles.get(path, ""))
    if chapters:
        return _merge_duplicate_epub_chapters(chapters, chapter_titles)
    return _fallback_epub_documents(archive, names)


def _fallback_epub_documents(
    archive: zipfile.ZipFile, names: set[str]
) -> tuple[list[str], list[str]]:
    documents = [
        _extract_html(archive.read(name))
        for name in sorted(names)
        if name.lower().endswith((".xhtml", ".html", ".htm"))
    ]
    return documents, [""] * len(documents)


def _document_title(document: str) -> str:
    first_line = next((line.strip() for line in document.splitlines() if line.strip()), "")
    return first_line if _CHAPTER_RE.fullmatch(first_line) else ""


def _chapter_number(title: str) -> str | None:
    match = re.search(r"第\s*(\d+)\s*(?:章|节|回)", title)
    return match.group(1) if match else None


def _merge_duplicate_epub_chapters(
    documents: list[str], titles: list[str]
) -> tuple[list[str], list[str]]:
    merged_documents: list[str] = []
    merged_titles: list[str] = []
    for document, title in zip(documents, titles, strict=True):
        display_title = title or _document_title(document)
        number = _chapter_number(display_title)
        if merged_titles and number is not None and number == _chapter_number(merged_titles[-1]):
            merged_documents[-1] = "\n\n".join(
                part for part in (merged_documents[-1], _remove_document_heading(document)) if part
            )
            if len(display_title) > len(merged_titles[-1]):
                merged_titles[-1] = display_title
            continue
        merged_documents.append(document)
        merged_titles.append(display_title)
    return merged_documents, merged_titles


def _remove_document_heading(document: str) -> str:
    lines = document.splitlines()
    for index, line in enumerate(lines):
        if line.strip():
            if _CHAPTER_RE.fullmatch(line.strip()):
                return "\n".join(lines[index + 1 :]).strip()
            break
    return document.strip()


def _epub_navigation_titles(
    archive: zipfile.ZipFile,
    manifest: dict[str, tuple[str, str, str]],
    names: set[str],
) -> dict[str, str]:
    titles: dict[str, str] = {}
    nav_item = next((item for item in manifest.values() if "nav" in item[2].split()), None)
    if nav_item and nav_item[0] in names:
        nav_root = ElementTree.fromstring(archive.read(nav_item[0]))
        for anchor in nav_root.iter():
            if not anchor.tag.endswith("a") or not anchor.attrib.get("href"):
                continue
            target = posixpath.normpath(
                posixpath.join(posixpath.dirname(nav_item[0]), urlsplit(anchor.attrib["href"]).path)
            )
            nav_label = " ".join("".join(anchor.itertext()).split())
            if nav_label:
                titles[target] = nav_label
    ncx = next(
        (item[0] for item in manifest.values() if item[1] == "application/x-dtbncx+xml"), None
    )
    if ncx and ncx in names:
        ncx_root = ElementTree.fromstring(archive.read(ncx))
        for point in ncx_root.iter():
            if not point.tag.endswith("navPoint"):
                continue
            content = next((child for child in point if child.tag.endswith("content")), None)
            ncx_label = next((child for child in point if child.tag.endswith("navLabel")), None)
            if content is not None and ncx_label is not None and content.attrib.get("src"):
                target = posixpath.normpath(
                    posixpath.join(posixpath.dirname(ncx), urlsplit(content.attrib["src"]).path)
                )
                titles.setdefault(target, " ".join("".join(ncx_label.itertext()).split()))
    return titles
