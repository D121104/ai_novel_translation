from __future__ import annotations

from pydantic import BaseModel, Field

from src.llm.provider import LLMProvider
from src.translation.context import TranslationContext


class SemanticQAIssue(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: str = "error"
    repairable: bool = True


class SemanticQAReport(BaseModel):
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    issues: list[SemanticQAIssue] = Field(default_factory=list)


class SemanticQA:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def run(
        self, source: str, translation: str, context: TranslationContext
    ) -> SemanticQAReport:
        prompt = (
            "Evaluate this Vietnamese translation against the source. Check omission, "
            "hallucination, meaning, pronouns, terminology, voice, fluency, and identity leakage.\n"
            "Return only JSON matching the requested schema.\n\n"
            f"CONTEXT:\n{context.to_prompt()}\n\n"
            f"SOURCE:\n{source}\n\nTRANSLATION:\n{translation}"
        )
        report, _ = await self._provider.generate_structured(prompt, SemanticQAReport)
        return report
