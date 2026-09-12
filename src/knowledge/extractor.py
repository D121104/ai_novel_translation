import re
from dataclasses import dataclass
from typing import Protocol

from src.knowledge.schemas import Evidence, ExtractionProposal
from src.llm.provider import LLMProvider, LLMResponse


class _EvidenceBearing(Protocol):
    evidence: list[Evidence]


@dataclass(frozen=True)
class ExtractionResult:
    proposal: ExtractionProposal
    response: LLMResponse
    unit_id: str


class KnowledgeExtractor:
    """Turns model proposals into validated, evidence-bound candidates."""

    def __init__(self, provider: LLMProvider, *, validation_retries: int = 1) -> None:
        if validation_retries < 0:
            raise ValueError("validation_retries must be non-negative")
        self._provider = provider
        self._validation_retries = validation_retries

    async def extract(self, unit_id: str, source_order: int, source_text: str) -> ExtractionResult:
        prompt = (
            "Extract entities, aliases, facts, relations, events, and terminology "
            "from the source. Every candidate must cite the supplied unit_id and an "
            "exact quote. Do not infer facts.\n"
            f"unit_id={unit_id}\nsource_order={source_order}\nsource:\n{source_text}"
        )
        last_error: ValueError | None = None
        for attempt in range(self._validation_retries + 1):
            attempt_prompt = prompt
            if attempt > 0:
                attempt_prompt += (
                    "\n\nThe previous response failed evidence validation. "
                    "Retry the extraction and copy every evidence.quote exactly, "
                    "character-for-character, from the supplied source."
                )
            proposal, response = await self._provider.generate_structured(
                attempt_prompt, ExtractionProposal
            )
            try:
                self._validate_evidence(proposal, unit_id, source_order, source_text)
            except ValueError as exc:
                last_error = exc
                continue
            return ExtractionResult(proposal, response, unit_id)
        assert last_error is not None
        raise last_error

    @staticmethod
    def _validate_evidence(
        proposal: ExtractionProposal, unit_id: str, source_order: int, source_text: str
    ) -> None:
        candidates: tuple[_EvidenceBearing, ...] = (
            *proposal.entities,
            *proposal.aliases,
            *proposal.facts,
            *proposal.relations,
            *proposal.events,
            *proposal.terminology,
        )
        for candidate in candidates:
            for evidence in candidate.evidence:
                if evidence.unit_id != unit_id or evidence.source_order != source_order:
                    raise ValueError("extraction evidence is not bound to the current unit")
                if evidence.quote not in source_text and _compact_text(
                    evidence.quote
                ) not in _compact_text(source_text):
                    quote_preview = evidence.quote[:200]
                    raise ValueError(
                        "extraction evidence quote is not present in source "
                        f"(unit_id={unit_id}, source_order={source_order}, "
                        f"quote={quote_preview!r})"
                    )


def _compact_text(value: str) -> str:
    """Ignore layout whitespace while preserving all non-whitespace characters."""
    return re.sub(r"\s+", "", value)
