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

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def extract(self, unit_id: str, source_order: int, source_text: str) -> ExtractionResult:
        prompt = (
            "Extract entities, aliases, facts, relations, events, and terminology "
            "from the source. Every candidate must cite the supplied unit_id and an "
            "exact quote. Do not infer facts.\n"
            f"unit_id={unit_id}\nsource_order={source_order}\nsource:\n{source_text}"
        )
        proposal, response = await self._provider.generate_structured(prompt, ExtractionProposal)
        self._validate_evidence(proposal, unit_id, source_order, source_text)
        return ExtractionResult(proposal, response, unit_id)

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
                if evidence.quote not in source_text:
                    raise ValueError("extraction evidence quote is not present in source")
