import pytest

from src.knowledge.extractor import KnowledgeExtractor
from src.knowledge.schemas import ExtractionProposal
from src.llm.provider import LLMResponse


class FakeProvider:
    async def generate_structured(self, prompt, schema):
        proposal = ExtractionProposal.model_validate(
            {
                "entities": [
                    {
                        "name": "Lan",
                        "entity_type": "character",
                        "evidence": [{"unit_id": "u1", "quote": "Lan entered", "source_order": 3}],
                    }
                ]
            }
        )
        return proposal, LLMResponse("{}", "test", 2, 1)


@pytest.mark.asyncio
async def test_extraction_returns_structured_evidence() -> None:
    result = await KnowledgeExtractor(FakeProvider()).extract("u1", 3, "Lan entered the room.")
    assert result.proposal.entities[0].evidence[0].unit_id == "u1"


@pytest.mark.asyncio
async def test_extraction_rejects_future_or_wrong_unit_evidence() -> None:
    class WrongProvider(FakeProvider):
        async def generate_structured(self, prompt, schema):
            proposal, response = await super().generate_structured(prompt, schema)
            proposal.entities[0].evidence[0] = (
                proposal.entities[0].evidence[0].model_copy(update={"source_order": 4})
            )
            return proposal, response

    with pytest.raises(ValueError, match="not bound"):
        await KnowledgeExtractor(WrongProvider()).extract("u1", 3, "Lan entered the room.")
