import pytest

from src.retrieval.memory import HashEmbedder, hybrid_fusion, sparse_terms


@pytest.mark.asyncio
async def test_hash_embedding_is_deterministic() -> None:
    embedder = HashEmbedder(8)
    assert await embedder.embed("Lan enters") == await embedder.embed("Lan enters")
    assert await embedder.embed_many(["Lan enters"]) == [await embedder.embed("Lan enters")]


def test_sparse_and_hybrid_fusion() -> None:
    assert sparse_terms("Lan lan enters") == {"lan": 2, "enters": 1}
    result = hybrid_fusion([("future", 1.0), ("past", 0.5)], [("past", 1.0)])
    assert result[0][0] == "future"
