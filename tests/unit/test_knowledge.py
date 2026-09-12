import pytest

from src.knowledge.extractor import KnowledgeExtractor
from src.knowledge.schemas import EntityCandidate, Evidence, ExtractionProposal
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


def test_extraction_accepts_layout_whitespace_in_evidence() -> None:
    source = "国内（\n第二大区\n）守序职业\n主要包括金木水火土五行"
    proposal = ExtractionProposal(
        entities=[
            EntityCandidate(
                name="职业",
                entity_type="term",
                evidence=[
                    Evidence(
                        unit_id="u1",
                        source_order=3,
                        quote="国内（第二大区）守序职业主要包括金木水火土五行",
                    )
                ],
            )
        ]
    )

    KnowledgeExtractor._validate_evidence(proposal, "u1", 3, source)


@pytest.mark.asyncio
async def test_extraction_retries_invalid_quote_before_failing() -> None:
    class InvalidThenValidProvider(FakeProvider):
        def __init__(self) -> None:
            self.calls = 0
            self.prompts: list[str] = []

        async def generate_structured(self, prompt, schema):
            self.calls += 1
            self.prompts.append(prompt)
            proposal, response = await super().generate_structured(prompt, schema)
            if self.calls == 1:
                proposal.entities[0].evidence[0] = (
                    proposal.entities[0].evidence[0].model_copy(update={"quote": "not in source"})
                )
            return proposal, response

    provider = InvalidThenValidProvider()
    result = await KnowledgeExtractor(provider).extract("u1", 3, "Lan entered the room.")

    assert result.proposal.entities[0].evidence[0].quote == "Lan entered"
    assert provider.calls == 2
    assert "copy every evidence.quote exactly" in provider.prompts[1]


@pytest.mark.asyncio
async def test_extraction_reports_invalid_quote_details() -> None:
    class WrongQuoteProvider(FakeProvider):
        async def generate_structured(self, prompt, schema):
            proposal, response = await super().generate_structured(prompt, schema)
            proposal.entities[0].evidence[0] = (
                proposal.entities[0].evidence[0].model_copy(update={"quote": "hallucinated quote"})
            )
            return proposal, response

    with pytest.raises(ValueError, match="hallucinated quote"):
        await KnowledgeExtractor(WrongQuoteProvider(), validation_retries=0).extract(
            "u1", 3, "Lan entered the room."
        )


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
