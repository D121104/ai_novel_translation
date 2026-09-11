from dataclasses import dataclass

from src.llm.provider import LLMProvider
from src.qa.deterministic import QAReport, deterministic_qa
from src.translation.context import GlossaryTerm


@dataclass(frozen=True)
class RepairAttempt:
    text: str
    report: QAReport


class RepairLoop:
    def __init__(self, provider: LLMProvider, *, max_attempts: int = 2) -> None:
        self._provider = provider
        self._max_attempts = max_attempts

    async def run(
        self,
        source: str,
        translation: str,
        *,
        names: tuple[str, ...] = (),
        glossary: tuple[GlossaryTerm, ...] = (),
    ) -> tuple[str, tuple[RepairAttempt, ...]]:
        history: list[RepairAttempt] = []
        current = translation
        for _ in range(self._max_attempts + 1):
            report = deterministic_qa(source, current, names=names, glossary=glossary)
            history.append(RepairAttempt(current, report))
            if report.passed:
                break
            prompt = (
                f"Repair this translation according to QA issues {report.issues}. "
                f"Return only repaired text.\n{current}"
            )
            current = (await self._provider.generate(prompt)).text.strip()
        return current, tuple(history)
