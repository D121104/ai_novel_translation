import os

import pytest

from src.core.config import Settings
from src.infrastructure.minio.health import check as minio_check
from src.infrastructure.neo4j.health import check as neo4j_check
from src.infrastructure.postgres.health import check as postgres_check
from src.infrastructure.qdrant.health import check as qdrant_check
from src.infrastructure.redis.health import check as redis_check

pytestmark = pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="set RUN_INTEGRATION=1")


@pytest.mark.asyncio
async def test_postgres_health() -> None:
    assert await postgres_check(Settings())


@pytest.mark.asyncio
async def test_neo4j_health() -> None:
    assert await neo4j_check(Settings())


@pytest.mark.asyncio
async def test_qdrant_health() -> None:
    assert await qdrant_check(Settings())


@pytest.mark.asyncio
async def test_redis_health() -> None:
    assert await redis_check(Settings())


@pytest.mark.asyncio
async def test_minio_health() -> None:
    assert await minio_check(Settings())
