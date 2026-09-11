from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from apps.api.schemas import ChapterResponse, NovelResponse, Paginated, ReviewAction
from src.core.config import get_settings
from src.core.logging import configure_logging
from src.core.operations import Metrics, disk_status
from src.domain.novel.models import AuditLog, Chapter, Novel, TranslationUnit
from src.exporter.formats import ExportChapter, ExportNovel, export_epub, export_json, export_txt
from src.infrastructure.health import check_dependencies
from src.infrastructure.minio.health import check as minio_check
from src.infrastructure.neo4j.health import check as neo4j_check
from src.infrastructure.neo4j.temporal_graph import TemporalGraph
from src.infrastructure.postgres.health import check as postgres_check
from src.infrastructure.postgres.migrations import apply_migrations
from src.infrastructure.postgres.repository import (
    PostgresNovelRepository,
    create_schema,
    session_factory,
)
from src.infrastructure.qdrant.health import check as qdrant_check
from src.infrastructure.redis.health import check as redis_check
from src.retrieval.memory import QdrantMemory

metrics = Metrics()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not (settings.performance_initialize_on_startup or settings.run_migrations_on_startup):
        yield
        return

    engine, _sessions = session_factory(settings)
    graph = TemporalGraph(settings)
    memory = QdrantMemory(settings)
    try:
        if settings.run_migrations_on_startup:
            await create_schema(engine)
            await apply_migrations(engine)
        if settings.performance_initialize_on_startup:
            await graph.ensure_indexes()
            await memory.ensure_collections()
        yield
    finally:
        await memory.close()
        await graph.close()
        await engine.dispose()


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics_endpoint() -> dict[str, object]:
    disk = disk_status(".", minimum_free_bytes=get_settings().disk_alert_min_free_bytes)
    return {"counters": metrics.snapshot(), "disk": disk.__dict__}


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


@app.get("/api/v1/novels", response_model=Paginated[NovelResponse], tags=["novels"])
async def list_novels(
    offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)
) -> Paginated[NovelResponse]:
    engine, sessions = session_factory(get_settings())
    try:
        async with sessions() as session:
            total = int(await session.scalar(select(func.count()).select_from(Novel)) or 0)
            records = (
                await session.scalars(
                    select(Novel).order_by(Novel.created_at).offset(offset).limit(limit)
                )
            ).all()
            return Paginated(
                items=[
                    NovelResponse.model_validate(record, from_attributes=True) for record in records
                ],
                offset=offset,
                limit=limit,
                total=total,
            )
    finally:
        await engine.dispose()


@app.get(
    "/api/v1/novels/{novel_id}/chapters",
    response_model=Paginated[ChapterResponse],
    tags=["chapters"],
)
async def list_chapters(
    novel_id: UUID, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)
) -> Paginated[ChapterResponse]:
    engine, sessions = session_factory(get_settings())
    try:
        async with sessions() as session:
            query = (
                select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.chapter_index)
            )
            total = int(
                await session.scalar(
                    select(func.count()).select_from(Chapter).where(Chapter.novel_id == novel_id)
                )
                or 0
            )
            records = (await session.scalars(query.offset(offset).limit(limit))).all()
            return Paginated(
                items=[
                    ChapterResponse.model_validate(record, from_attributes=True)
                    for record in records
                ],
                offset=offset,
                limit=limit,
                total=total,
            )
    finally:
        await engine.dispose()


@app.post("/api/v1/review/actions", tags=["review"])
async def review_action(action: ReviewAction) -> dict[str, str]:
    engine, sessions = session_factory(get_settings())
    try:
        await create_schema(engine)
        async with sessions() as session:
            session.add(AuditLog(**action.model_dump()))
            await session.commit()
        return {"status": "recorded", "action": action.action}
    finally:
        await engine.dispose()


@app.get("/api/v1/novels/{novel_id}/export", tags=["export"])
async def export_novel(
    novel_id: UUID,
    format: str = Query("txt", pattern="^(txt|json|epub)$"),
    bilingual: bool = False,
) -> Response:
    engine, sessions = session_factory(get_settings())
    try:
        async with sessions() as session:
            query = (
                select(Novel)
                .options(
                    selectinload(Novel.chapters)
                    .selectinload(Chapter.units)
                    .selectinload(TranslationUnit.translations)
                )
                .where(Novel.id == novel_id)
            )
            novel = await session.scalar(query)
            if novel is None:
                raise HTTPException(status_code=404, detail="novel not found")
            chapters = []
            for chapter in sorted(novel.chapters, key=lambda item: item.chapter_index):
                translations = [
                    translation for unit in chapter.units for translation in unit.translations
                ]
                latest = (
                    max(translations, key=lambda item: item.version).translated_text
                    if translations
                    else None
                )
                chapters.append(
                    ExportChapter(chapter.chapter_index, chapter.title, chapter.source_text, latest)
                )
            export = ExportNovel(
                novel.title,
                novel.author,
                novel.source_language,
                novel.target_language,
                tuple(chapters),
            )
            exporters = {"txt": export_txt, "json": export_json, "epub": export_epub}
            content = exporters[format](export, bilingual=bilingual)
            media_types = {
                "txt": "text/plain",
                "json": "application/json",
                "epub": "application/epub+zip",
            }
            return Response(content, media_type=media_types[format])
    finally:
        await engine.dispose()
