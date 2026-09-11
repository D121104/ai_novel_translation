import pytest

from src.graphrag.retriever import GraphRAGRetriever, recall_at_k
from src.retrieval.memory import MemoryPoint
from src.summaries.models import StorySummary, SummaryLevel


class Graph:
    async def active_relations(self, entity_id, as_of_order):
        return [{"entity": entity_id, "order": as_of_order}]


class Vectors:
    async def search(self, collection, query, *, as_of_order, limit=10):
        return [MemoryPoint("past", "past character fact", 1, {})]


@pytest.mark.asyncio
async def test_graphrag_context_is_temporally_bounded() -> None:
    future = StorySummary(
        summary_id="future",
        level=SummaryLevel.CHAPTER,
        narrative="future secret",
        start_order=10,
        end_order=10,
    )
    context = await GraphRAGRetriever(Graph(), Vectors()).retrieve(
        "character fact", entity_ids=["e1"], as_of_order=5, summaries=[future]
    )
    assert "future secret" not in context.text
    assert "past character fact" in context.text
    assert context.as_of_order == 5


def test_recall_at_k() -> None:
    assert recall_at_k(["a", "b", "c"], {"b"}, 2) == 1.0
