import io
import json
import re
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


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


_CHAPTER_RE = re.compile(r"(?im)^\s*((?:chapter|chương)\s+[^\n]{1,160})\s*$")


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
            names = sorted(
                name
                for name in archive.namelist()
                if name.lower().endswith((".xhtml", ".html", ".htm"))
            )
            text = "\n".join(_extract_html(archive.read(name)) for name in names)
        return ParsedNovel(Path(filename).stem, None, detect_chapters(text))
    text = normalize_text(data)
    return ParsedNovel(Path(filename).stem, None, detect_chapters(text))


def _extract_html(data: bytes) -> str:
    parser = _TextExtractor()
    parser.feed(normalize_text(data))
    return parser.text()
