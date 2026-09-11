import asyncio

from minio import Minio

from src.core.config import Settings


async def check(settings: Settings) -> bool:
    def ping() -> bool:
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key.get_secret_value(),
            secure=settings.minio_secure,
        )
        client.list_buckets()
        return True

    return await asyncio.wait_for(asyncio.to_thread(ping), settings.health_timeout_seconds)
