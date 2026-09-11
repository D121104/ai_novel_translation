import redis.asyncio as redis

from src.core.config import Settings


async def check(settings: Settings) -> bool:
    client = redis.from_url(
        settings.redis_url,
        socket_connect_timeout=settings.health_timeout_seconds,
        socket_timeout=settings.health_timeout_seconds,
    )  # type: ignore[no-untyped-call]
    try:
        return (await client.ping()) is True
    finally:
        await client.aclose()
