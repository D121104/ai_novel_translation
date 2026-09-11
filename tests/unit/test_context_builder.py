from uuid import uuid4

import pytest

from src.domain.novel.models import TranslationUnit
from src.graphrag.retriever import ContextItem, RetrievalContext
from src.translation.context import AddressingRule, GlossaryTerm
from src.translation.context_builder import RuntimeContextBuilder


class Metadata:
    async def glossary(self, novel_id):
        return (GlossaryTerm("sword", "kiếm"),)

    async def names(self, novel_id, *, as_of_order):
        return ("Lan",)

    async def addressing(self, novel_id, *, as_of_order):
        return (AddressingRule("Lan", "Minh", "ta", "ngươi"),)

    async def entity_ids(self, novel_id, source, *, as_of_order):
        return ["entity-lan"]


class Retriever:
    async def retrieve(self, query, *, entity_ids, as_of_order, novel_id=None):
        assert entity_ids == ["entity-lan"]
        assert novel_id is not None
        return RetrievalContext(
            (
                ContextItem("graph", "Lan knows Minh", 0.9, as_of_order),
                ContextItem("translation_memory", "Lan cầm kiếm", 0.8, as_of_order - 1),
            ),
            as_of_order,
        )


@pytest.mark.asyncio
async def test_runtime_context_builder_wires_metadata_and_graphrag() -> None:
    novel_id = uuid4()
    unit = TranslationUnit(
        id=uuid4(),
        chapter_id=uuid4(),
        unit_index=0,
        source_order=1_000_001,
        source_text="Lan uses a sword.",
        token_count=5,
        status="pending",
    )

    context = await RuntimeContextBuilder(Retriever(), Metadata()).build(
        novel_id=novel_id,
        unit=unit,
        as_of_order=unit.source_order,
        previous="Trước đó.",
    )

    assert context.glossary == (GlossaryTerm("sword", "kiếm"),)
    assert context.names == ("Lan",)
    assert context.addressing[0].listener_pronoun == "ngươi"
    assert context.previous == "Trước đó."
    assert context.graph_facts == ("Lan knows Minh",)
    assert context.memories == ("Lan cầm kiếm",)
