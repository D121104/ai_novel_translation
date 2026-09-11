from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from src.core.config import get_settings
from src.core.logging import configure_logging
from src.infrastructure.health import check_dependencies
from src.infrastructure.minio.health import check as minio_check
from src.infrastructure.neo4j.health import check as neo4j_check
from src.infrastructure.postgres.health import check as postgres_check
from src.infrastructure.postgres.repository import (
    PostgresNovelRepository,
    create_schema,
    session_factory,
)
from src.infrastructure.qdrant.health import check as qdrant_check
from src.infrastructure.redis.health import check as redis_check


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(get_settings().log_level)
    yield


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, Any]:
    settings = get_settings()
    dependencies = await check_dependencies(
        {
            "postgres": lambda: postgres_check(settings),
            "neo4j": lambda: neo4j_check(settings),
            "qdrant": lambda: qdrant_check(settings),
            "redis": lambda: redis_check(settings),
            "minio": lambda: minio_check(settings),
        }
    )
    payload: dict[str, Any] = {"status": "ready", "dependencies": dependencies}
    if any(status != "ok" for status in dependencies.values()):
        payload["status"] = "not_ready"
        raise HTTPException(status_code=503, detail=payload)
    return payload


@app.post("/imports")
async def import_novel(request: Request, filename: str = "novel.txt") -> dict[str, Any]:
    settings = get_settings()
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="request body is empty")
    engine, sessions = session_factory(settings)
    try:
        await create_schema(engine)
        async with sessions() as session:
            from src.ingestion.service import ImportService
            from src.ingestion.storage import MinioStorage

            report = await ImportService(
                PostgresNovelRepository(session), MinioStorage(settings)
            ).import_file(filename, data)
        return report.__dict__
    finally:
        await engine.dispose()
