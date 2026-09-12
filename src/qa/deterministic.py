import re
from dataclasses import dataclass
from html.parser import HTMLParser

from src.translation.context import GlossaryTerm

_UNCLOSED_TAG_PATTERN = re.compile(r"</?[A-Za-z][^>]*$")
_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}


class _MarkupBalanceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.open_tags: list[str] = []
        self.malformed = False

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag not in _VOID_TAGS:
            self.open_tags.append(tag)

    def handle_startendtag(self, _tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        return

    def handle_endtag(self, tag: str) -> None:
        if not self.open_tags or self.open_tags[-1] != tag:
            self.malformed = True
            return
        self.open_tags.pop()


def _has_malformed_markup(text: str) -> bool:
    parser = _MarkupBalanceParser()
    parser.feed(text)
    parser.close()
    return parser.malformed or bool(parser.open_tags) or bool(_UNCLOSED_TAG_PATTERN.search(text))


@dataclass(frozen=True)
class QAIssue:
    code: str
    message: str
    severity: str = "error"


@dataclass(frozen=True)
class QAReport:
    issues: tuple[QAIssue, ...]
    score: float

    @property
    def passed(self) -> bool:
        return not self.issues


def deterministic_qa(
    source: str,
    translation: str,
    *,
    names: tuple[str, ...] = (),
    glossary: tuple[GlossaryTerm, ...] = (),
) -> QAReport:
    issues: list[QAIssue] = []
    if not translation.strip():
        issues.append(QAIssue("empty", "translation is empty"))
    source_paragraphs = [part for part in source.split("\n\n") if part.strip()]
    translation_paragraphs = [part for part in translation.split("\n\n") if part.strip()]
    if len(translation_paragraphs) < len(source_paragraphs):
        issues.append(QAIssue("missing_paragraph", "translation has fewer paragraphs"))
    for name in names:
        if name in source and name not in translation:
            issues.append(QAIssue("wrong_name", f"proper name missing: {name}"))
    for term in glossary:
        if term.locked and term.source in source and term.target not in translation:
            issues.append(QAIssue("glossary_violation", f"locked term missing: {term.target}"))
    if re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]{4,}", translation):
        issues.append(
            QAIssue("untranslated_cjk", "translation contains an untranslated CJK segment")
        )
    if _has_malformed_markup(translation):
        issues.append(QAIssue("malformed_markup", "unbalanced markup"))
    if source.strip() and len(translation) > max(len(source) * 5, 1000):
        issues.append(QAIssue("length_anomaly", "translation is unusually long"))
    return QAReport(tuple(issues), max(0.0, 1.0 - 0.15 * len(issues)))
