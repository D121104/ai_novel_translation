import re
from dataclasses import dataclass
from typing import Any, Protocol

from src.retrieval.memory import MemoryPoint
from src.summaries.models import StorySummary, visible_summaries


class GraphReader(Protocol):
    async def active_relations(self, entity_id: str, as_of_order: int) -> list[dict[str, Any]]: ...


class VectorReader(Protocol):
    async def search(
        self,
        collection: str,
        query: str,
        *,
        as_of_order: int,
        novel_id: str | None = None,
        limit: int = 10,
    ) -> list[MemoryPoint]: ...


@dataclass(frozen=True)
class ContextItem:
    kind: str
    text: str
    score: float
    story_order: int


@dataclass(frozen=True)
class RetrievalContext:
    items: tuple[ContextItem, ...]
    as_of_order: int

    @property
    def text(self) -> str:
        return "\n\n".join(item.text for item in self.items)


class GraphRAGRetriever:
    def __init__(self, graph: GraphReader, vectors: VectorReader) -> None:
        self._graph = graph
        self._vectors = vectors

    async def retrieve(
        self,
        query: str,
        *,
        entity_ids: list[str],
        as_of_order: int,
        novel_id: str | None = None,
        summaries: list[StorySummary] | None = None,
        max_items: int = 12,
        max_tokens: int = 4000,
    ) -> RetrievalContext:
        items: list[ContextItem] = []
        summaries = summaries or []
        for entity_id in entity_ids:
            for relation in await self._graph.active_relations(entity_id, as_of_order):
                observed_at = int(relation.get("observed_at_order", as_of_order))
                if observed_at <= as_of_order:
                    items.append(ContextItem("graph", str(relation), 0.9, observed_at))
        for collection, kind, visible_order in (
            ("novel_chunks", "vector", as_of_order),
            ("translation_memory", "translation_memory", as_of_order - 1),
        ):
            if novel_id is None:
                points = await self._vectors.search(collection, query, as_of_order=visible_order)
            else:
                points = await self._vectors.search(
                    collection,
                    query,
                    as_of_order=visible_order,
                    novel_id=novel_id,
                )
            for point in points:
                if point.story_order <= visible_order:
                    items.append(ContextItem(kind, point.text, 0.8, point.story_order))
        for summary in visible_summaries(summaries, as_of_order=as_of_order, limit=max_items):
            items.append(ContextItem("summary", summary.narrative, 0.7, summary.end_order))
        ranked = sorted(
            items, key=lambda item: _lexical_score(query, item.text) + item.score, reverse=True
        )
        selected: list[ContextItem] = []
        budget = 0
        for item in ranked:
            cost = len(re.findall(r"\S+", item.text))
            if len(selected) >= max_items or budget + cost > max_tokens:
                continue
            selected.append(item)
            budget += cost
        return RetrievalContext(tuple(selected), as_of_order)


def _lexical_score(query: str, text: str) -> float:
    query_terms = set(re.findall(r"\w+", query.casefold()))
    text_terms = set(re.findall(r"\w+", text.casefold()))
    return len(query_terms & text_terms) / max(len(query_terms), 1)


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 1.0
    return len(set(retrieved_ids[:k]) & relevant_ids) / len(relevant_ids)
