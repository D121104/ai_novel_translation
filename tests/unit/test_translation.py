import pytest

from src.llm.provider import LLMResponse
from src.translation.context import GlossaryTerm, TranslationContext
from src.translation.engine import Translator


class Provider:
    async def generate(self, prompt, *, system=None):
        return LLMResponse("The hero uses sword.", "test", 5, 4)


class Store:
    def __init__(self):
        self.saved = None

    async def save(self, unit_id, text, version):
        self.saved = (unit_id, text, version)


@pytest.mark.asyncio
async def test_translation_enforces_locked_glossary_and_persists_version() -> None:
    store = Store()
    result = await Translator(Provider(), store).translate(
        "u1", TranslationContext("source", glossary=(GlossaryTerm("sword", "kiếm"),)), version=2
    )
    assert result.text == "The hero uses kiếm."
    assert store.saved == ("u1", "The hero uses kiếm.", 2)


def test_context_keeps_source_when_budget_is_small() -> None:
    context = TranslationContext("one two three", previous="old context", memories=("memory",))
    prompt = context.to_prompt(max_tokens=3)
    assert "one two three" in prompt
    assert "old context" not in prompt
