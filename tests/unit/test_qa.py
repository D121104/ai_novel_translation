import pytest

from src.llm.provider import LLMResponse
from src.qa.deterministic import deterministic_qa
from src.qa.repair import RepairLoop
from src.translation.context import GlossaryTerm


def test_qa_ignores_numeric_differences() -> None:
    report = deterministic_qa(
        "Lan has 12 swords.",
        "Lan có 13 thanh gươm.",
    )
    assert report.passed


def test_qa_accepts_valid_translation() -> None:
    report = deterministic_qa("Lan has 12 swords.", "Lan có 12 kiếm.", names=("Lan",))
    assert report.passed


def test_qa_catches_untranslated_cjk_segment() -> None:
    report = deterministic_qa("这是一段中文内容。", "这是一段中文内容。")
    assert "untranslated_cjk" in {issue.code for issue in report.issues}


def test_qa_does_not_treat_arrows_as_markup() -> None:
    report = deterministic_qa("First stage", "First stage ----> Second stage")

    assert report.passed


def test_qa_catches_unbalanced_markup() -> None:
    report = deterministic_qa("<p>First stage</p>", "<p>First stage")

    assert "malformed_markup" in {issue.code for issue in report.issues}


class CaptureProvider:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        self.prompts.append(prompt)
        return LLMResponse("Lan có 12 kiếm và 12 cung.", "fake-model", 1, 6)


@pytest.mark.asyncio
async def test_repair_prompt_contains_source_and_qa_issues() -> None:
    provider = CaptureProvider()
    await RepairLoop(provider, max_attempts=1).run(
        "Lan has 12 swords and 12 bows.",
        "Lan có 13 thanh gươm và 12 cung.",
        names=("Lan",),
        glossary=(GlossaryTerm("swords", "kiếm"),),
    )

    assert len(provider.prompts) == 1
    prompt = provider.prompts[0]
    assert "Lan has 12 swords and 12 bows." in prompt
    assert "glossary_violation" in prompt
    assert "REQUIRED NUMERIC VALUES" not in prompt
    assert "CURRENT TRANSLATION:\nLan có 13 thanh gươm và 12 cung." in prompt
