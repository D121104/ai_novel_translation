import pytest

from src.llm.provider import LLMResponse
from src.qa.deterministic import deterministic_qa
from src.qa.repair import RepairLoop
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


def test_qa_catches_untranslated_cjk_segment() -> None:
    report = deterministic_qa("这是一段中文内容。", "这是一段中文内容。")
    assert "untranslated_cjk" in {issue.code for issue in report.issues}


class CaptureProvider:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        self.prompts.append(prompt)
        return LLMResponse("Lan có 12 kiếm và 12 cung.", "fake-model", 1, 6)


@pytest.mark.asyncio
async def test_repair_prompt_contains_source_and_required_numbers() -> None:
    provider = CaptureProvider()
    await RepairLoop(provider, max_attempts=1).run(
        "Lan has 12 swords and 12 bows.",
        "Lan có 13 kiếm và 12 cung.",
        names=("Lan",),
        glossary=(GlossaryTerm("swords", "kiếm"),),
    )

    assert len(provider.prompts) == 1
    prompt = provider.prompts[0]
    assert "Lan has 12 swords and 12 bows." in prompt
    assert "REQUIRED NUMERIC VALUES (preserve exact values and multiplicity):\n12, 12" in prompt
    assert "wrong_number" in prompt
    assert "CURRENT TRANSLATION:\nLan có 13 kiếm và 12 cung." in prompt
