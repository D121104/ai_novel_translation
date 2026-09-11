from qdrant_client import AsyncQdrantClient

from src.core.config import Settings


async def check(settings: Settings) -> bool:
    client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
        timeout=int(settings.health_timeout_seconds),
    )
    try:
        await client.get_collections()
        return True
    finally:
        await client.close()
