from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.core.config import Settings
from src.retrieval.memory import (
    HashEmbedder,
    MemoryPoint,
    QdrantMemory,
    hybrid_fusion,
    qdrant_point_id,
    sparse_terms,
)


@pytest.mark.asyncio
async def test_hash_embedding_is_deterministic() -> None:
    embedder = HashEmbedder(8)
    assert await embedder.embed("Lan enters") == await embedder.embed("Lan enters")
    assert await embedder.embed_many(["Lan enters"]) == [await embedder.embed("Lan enters")]


def test_sparse_and_hybrid_fusion() -> None:
    assert sparse_terms("Lan lan enters") == {"lan": 2, "enters": 1}
    result = hybrid_fusion([("future", 1.0), ("past", 0.5)], [("past", 1.0)])
    assert result[0][0] == "future"


def test_qdrant_point_id_is_deterministic_uuid() -> None:
    first = qdrant_point_id("source:unit-1")

    assert UUID(first).version == 5
    assert first == qdrant_point_id("source:unit-1")
    assert first != qdrant_point_id("source:unit-2")


@pytest.mark.asyncio
async def test_qdrant_upsert_uses_valid_id_and_preserves_logical_id() -> None:
    memory = QdrantMemory(Settings(), HashEmbedder(8))
    qdrant = SimpleNamespace(upsert=AsyncMock())
    memory._qdrant = qdrant

    await memory.upsert(
        "novel_chunks",
        MemoryPoint("source:unit-1", "Lan enters", 1, {"unit_id": "unit-1"}),
    )

    point = qdrant.upsert.await_args.args[1][0]
    assert UUID(str(point.id)).version == 5
    assert point.payload["memory_point_id"] == "source:unit-1"


@pytest.mark.asyncio
async def test_qdrant_search_restores_logical_id() -> None:
    logical_id = "source:unit-1"
    qdrant = SimpleNamespace(
        query_points=AsyncMock(
            return_value=SimpleNamespace(
                points=[
                    SimpleNamespace(
                        id=qdrant_point_id(logical_id),
                        score=1.0,
                        payload={
                            "memory_point_id": logical_id,
                            "text": "Lan enters",
                            "observed_at_order": 1,
                            "sparse": {"lan": 1, "enters": 1},
                        },
                    )
                ]
            )
        )
    )
    memory = QdrantMemory(Settings(), HashEmbedder(8))
    memory._qdrant = qdrant

    results = await memory.search("novel_chunks", "Lan", as_of_order=1)

    assert results[0].point_id == logical_id
