"""Reproducible local Phase 19 benchmark (no external services required)."""

import asyncio
import json

from src.core.performance import benchmark_async
from src.retrieval.memory import HashEmbedder


async def main() -> None:
    embedder = HashEmbedder()
    texts = [f"Character {index} enters the city." for index in range(100)]
    before = await benchmark_async(
        "embedding_serial_baseline",
        lambda: _serial(embedder, texts),
        iterations=10,
    )
    after = await benchmark_async(
        "embedding_batch_api",
        lambda: embedder.embed_many(texts),
        iterations=10,
    )
    print(json.dumps({"before": before.__dict__, "after": after.__dict__}, indent=2))


async def _serial(embedder: HashEmbedder, texts: list[str]) -> list[list[float]]:
    return [await embedder.embed(text) for text in texts]


if __name__ == "__main__":
    asyncio.run(main())
