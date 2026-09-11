from dataclasses import dataclass
from typing import Protocol

from src.llm.provider import LLMProvider
from src.translation.context import TranslationContext


class TranslationStore(Protocol):
    async def save(self, unit_id: str, text: str, version: int) -> None: ...


@dataclass(frozen=True)
class TranslationResult:
    unit_id: str
    text: str
    version: int
    response_model: str


class Translator:
    def __init__(self, provider: LLMProvider, store: TranslationStore) -> None:
        self._provider = provider
        self._store = store

    async def translate(
        self, unit_id: str, context: TranslationContext, *, version: int = 1
    ) -> TranslationResult:
        glossary = "\n".join(
            f"Always translate {term.source} as {term.target}."
            for term in context.glossary
            if term.locked
        )
        prompt = (
            "Translate into natural Vietnamese. Preserve meaning and formatting.\n"
            f"{glossary}\n\n{context.to_prompt()}"
        )
        response = await self._provider.generate(prompt)
        text = response.text.strip()
        if not text:
            raise ValueError("translation provider returned empty output")
        for term in context.glossary:
            if term.locked:
                text = text.replace(term.source, term.target)
        await self._store.save(unit_id, text, version)
        return TranslationResult(unit_id, text, version, response.model)
