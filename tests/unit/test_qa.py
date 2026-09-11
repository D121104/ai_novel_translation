from src.qa.deterministic import deterministic_qa
from src.translation.context import GlossaryTerm


def test_qa_catches_numbers_names_and_glossary() -> None:
    report = deterministic_qa(
        "Lan has 12 swords.",
        "Lan có 13 thanh gươm.",
        names=("Lan",),
        glossary=(GlossaryTerm("swords", "kiếm"),),
    )
    assert {issue.code for issue in report.issues} == {"wrong_number", "glossary_violation"}


def test_qa_accepts_valid_translation() -> None:
    report = deterministic_qa("Lan has 12 swords.", "Lan có 12 kiếm.", names=("Lan",))
    assert report.passed
