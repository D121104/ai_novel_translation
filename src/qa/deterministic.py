import re
from dataclasses import dataclass

from src.translation.context import GlossaryTerm

_NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)?")


def extract_numeric_values(text: str) -> tuple[str, ...]:
    """Return numeric values in source order, preserving duplicate values."""
    return tuple(_NUMBER_PATTERN.findall(text))


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
    source_numbers = extract_numeric_values(source)
    translation_numbers = extract_numeric_values(translation)
    if sorted(source_numbers) != sorted(translation_numbers):
        issues.append(QAIssue("wrong_number", "numeric values changed"))
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
    if re.search(r"<[^>]*$|^[^<]*>", translation):
        issues.append(QAIssue("malformed_markup", "unbalanced markup"))
    if source.strip() and len(translation) > max(len(source) * 5, 1000):
        issues.append(QAIssue("length_anomaly", "translation is unusually long"))
    return QAReport(tuple(issues), max(0.0, 1.0 - 0.15 * len(issues)))
