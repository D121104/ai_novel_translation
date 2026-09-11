import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Protocol

from qdrant_client import AsyncQdrantClient, models

from src.core.config import Settings

COLLECTIONS = ("novel_chunks", "translation_memory", "story_summaries")


class Embedder(Protocol):
    async def embed(self, text: str) -> list[float]: ...

    async def embed_many(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Deterministic local embedding baseline; replaceable by a real model later."""

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    async def embed(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in re.findall(r"\w+", text.casefold()):
            index = int(hashlib.sha256(token.encode()).hexdigest(), 16) % self.dimensions
            vector[index] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]


@dataclass(frozen=True)
class MemoryPoint:
    point_id: str
    text: str
    story_order: int
    payload: dict[str, Any]


def sparse_terms(text: str) -> dict[str, int]:
    return dict(Counter(re.findall(r"\w+", text.casefold())))


def hybrid_fusion(
    dense: list[tuple[str, float]], sparse: list[tuple[str, float]], *, dense_weight: float = 0.7
) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for point_id, score in dense:
        scores[point_id] = scores.get(point_id, 0.0) + dense_weight * score
    for point_id, score in sparse:
        scores[point_id] = scores.get(point_id, 0.0) + (1 - dense_weight) * score
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


class QdrantMemory:
    def __init__(self, settings: Settings, embedder: Embedder | None = None) -> None:
        self._settings = settings
        self._embedder = embedder or HashEmbedder()
        self._qdrant = self._new_client()

    async def close(self) -> None:
        await self._qdrant.close()

    async def ensure_collections(self) -> None:
        existing = {
            collection.name for collection in (await self._qdrant.get_collections()).collections
        }
        for name in COLLECTIONS:
            if name not in existing:
                await self._qdrant.create_collection(
                    name,
                    vectors_config=models.VectorParams(size=64, distance=models.Distance.COSINE),
                )
            await self._qdrant.create_payload_index(
                name,
                field_name="observed_at_order",
                field_schema=models.PayloadSchemaType.INTEGER,
            )

    async def upsert(self, collection: str, point: MemoryPoint) -> None:
        await self.upsert_many(collection, [point])

    async def upsert_many(self, collection: str, points: list[MemoryPoint]) -> None:
        if collection not in COLLECTIONS:
            raise ValueError(f"unsupported memory collection: {collection}")
        if not points:
            return
        vectors = await self._embedder.embed_many([point.text for point in points])
        await self._qdrant.upsert(
            collection,
            [
                models.PointStruct(
                    id=point.point_id,
                    vector=vector,
                    payload={
                        **point.payload,
                        "text": point.text,
                        "observed_at_order": point.story_order,
                        "sparse": sparse_terms(point.text),
                    },
                )
                for point, vector in zip(points, vectors, strict=True)
            ],
        )

    async def search(
        self, collection: str, query: str, *, as_of_order: int, limit: int = 10
    ) -> list[MemoryPoint]:
        if collection not in COLLECTIONS:
            raise ValueError(f"unsupported memory collection: {collection}")
        result = await self._qdrant.query_points(
            collection,
            query=await self._embedder.embed(query),
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="observed_at_order", range=models.Range(lte=as_of_order)
                    )
                ]
            ),
            limit=limit,
            with_payload=True,
        )
        points: list[MemoryPoint] = []
        for point in result.points:
            payload = dict(point.payload or {})
            points.append(
                MemoryPoint(
                    str(point.id),
                    str(payload.get("text", "")),
                    int(payload["observed_at_order"]),
                    payload,
                )
            )
        return points

    def _new_client(self) -> AsyncQdrantClient:
        return AsyncQdrantClient(
            url=self._settings.qdrant_url,
            api_key=self._settings.qdrant_api_key.get_secret_value()
            if self._settings.qdrant_api_key
            else None,
            timeout=int(self._settings.health_timeout_seconds),
        )
