from dataclasses import dataclass

from src.llm.provider import LLMProvider
from src.qa.deterministic import QAReport, deterministic_qa, extract_numeric_values
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
            required_numbers = ", ".join(extract_numeric_values(source)) or "(none)"
            locked_glossary = (
                "\n".join(f"{term.source} => {term.target}" for term in glossary if term.locked)
                or "(none)"
            )
            canonical_names = ", ".join(names) or "(none)"
            issues = "\n".join(f"- {issue.code}: {issue.message}" for issue in report.issues)
            prompt = (
                "Repair the Vietnamese translation using the authoritative source below.\n"
                "Preserve every paragraph, number, proper name, and locked glossary term.\n"
                "Do not add information. Return only the repaired Vietnamese text.\n\n"
                f"AUTHORITATIVE SOURCE:\n{source}\n\n"
                f"QA ISSUES:\n{issues}\n\n"
                f"REQUIRED NUMERIC VALUES (preserve exact values and multiplicity):\n"
                f"{required_numbers}\n\n"
                f"LOCKED GLOSSARY:\n{locked_glossary}\n\n"
                f"CANONICAL NAMES:\n{canonical_names}\n\n"
                f"CURRENT TRANSLATION:\n{current}"
            )
            current = (await self._provider.generate(prompt)).text.strip()
        return current, tuple(history)
