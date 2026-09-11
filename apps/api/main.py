from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from apps.api.schemas import (
    ChapterContentResponse,
    ChapterResponse,
    NovelResponse,
    NovelTranslationJobResponse,
    Paginated,
    ReviewAction,
    TranslationJobResponse,
    TranslationResponse,
    TranslationRunResponse,
    UnitContentResponse,
)
from src.core.config import get_settings
from src.core.logging import configure_logging
from src.core.operations import Metrics, disk_status
from src.domain.novel.models import (
    AuditLog,
    Chapter,
    Novel,
    NovelTranslationJob,
    Translation,
    TranslationJob,
    TranslationUnit,
)
from src.exporter.formats import ExportChapter, ExportNovel, export_epub, export_json, export_txt
from src.graphrag.retriever import GraphRAGRetriever
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
from src.ingestion.storage import MinioStorage
from src.knowledge.extractor import KnowledgeExtractor
from src.knowledge.pipeline import PostgresKnowledgeStage
from src.llm.provider import create_provider
from src.qa.semantic import SemanticQA
from src.retrieval.memory import QdrantMemory
from src.summaries.builder import SummaryBuilder
from src.summaries.store import PostgresSummaryStage
from src.translation.context_builder import PostgresMetadataSource, RuntimeContextBuilder
from src.translation.service import (
    TranslationOrderBlocked,
    TranslationQAFailure,
    TranslationSemanticFailure,
    TranslationService,
)

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


@app.get(
    "/api/v1/chapters/{chapter_id}/content",
    response_model=ChapterContentResponse,
    tags=["chapters"],
)
async def chapter_content(chapter_id: UUID) -> ChapterContentResponse:
    engine, sessions = session_factory(get_settings())
    try:
        async with sessions() as session:
            chapter = await session.scalar(
                select(Chapter)
                .options(selectinload(Chapter.units).selectinload(TranslationUnit.translations))
                .where(Chapter.id == chapter_id)
            )
            if chapter is None:
                raise HTTPException(status_code=404, detail="chapter not found")
            units = sorted(chapter.units, key=lambda item: (item.source_order, item.unit_index))
            return ChapterContentResponse(
                id=chapter.id,
                chapter_index=chapter.chapter_index,
                title=chapter.title,
                source_text=chapter.source_text,
                units=[
                    UnitContentResponse(
                        unit_id=unit.id,
                        unit_index=unit.unit_index,
                        source_text=unit.source_text,
                        translated_text=(
                            max(unit.translations, key=lambda item: item.version).translated_text
                            if unit.translations
                            else None
                        ),
                    )
                    for unit in units
                ],
            )
    finally:
        await engine.dispose()


@app.delete("/api/v1/novels/{novel_id}", tags=["novels"])
async def delete_novel(novel_id: UUID) -> dict[str, str]:
    engine, sessions = session_factory(get_settings())
    try:
        async with sessions() as session:
            novel = await session.get(Novel, novel_id)
            if novel is None:
                raise HTTPException(status_code=404, detail="novel not found")
            await session.delete(novel)
            await session.commit()
            return {"status": "deleted", "novel_id": str(novel_id)}
    finally:
        await engine.dispose()


async def _run_translation(
    chapter_id: UUID, *, retry_failed: bool = False, job_id: UUID | None = None
) -> TranslationRunResponse:
    settings = get_settings()
    engine, sessions = session_factory(settings)
    graph: TemporalGraph | None = None
    memory: QdrantMemory | None = None
    try:
        await create_schema(engine)
        async with sessions() as session:
            try:
                graph = TemporalGraph(settings)
                memory = QdrantMemory(settings)
                await memory.ensure_collections()
                context_builder = RuntimeContextBuilder(
                    GraphRAGRetriever(graph, memory), PostgresMetadataSource(session), memory
                )
                provider = create_provider(settings)

                async def mark_unit_started(unit_id: UUID) -> None:
                    if job_id is None:
                        return
                    job = await session.get(TranslationJob, job_id)
                    if job is not None:
                        job.current_unit_id = unit_id
                        job.lease_until = datetime.now(UTC) + timedelta(
                            minutes=settings.translation_lease_minutes
                        )
                        await session.commit()

                service = TranslationService(
                    session,
                    settings,
                    provider=provider,
                    context_builder=context_builder,
                    memory_sink=memory,
                    knowledge_stage=PostgresKnowledgeStage(
                        session, KnowledgeExtractor(provider), graph
                    ),
                    semantic_qa=SemanticQA(provider),
                    on_unit_started=mark_unit_started,
                    summary_stage=PostgresSummaryStage(session, SummaryBuilder(provider), memory),
                )
                if retry_failed:
                    result = await service.translate_chapter(chapter_id, retry_failed=True)
                else:
                    result = await service.translate_chapter(chapter_id)
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except TranslationQAFailure as exc:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "translation_qa_failed",
                        "chapter_id": str(exc.chapter_id),
                        "unit_id": str(exc.unit_id),
                        "unit_index": exc.unit_index,
                        "processed": exc.processed,
                        "failed": 1,
                        "status": "failed",
                        "issues": [issue.__dict__ for issue in exc.report.issues],
                    },
                ) from exc
            except TranslationOrderBlocked as exc:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "translation_order_blocked",
                        "unit_id": str(exc.unit_id),
                        "unit_index": exc.unit_index,
                        "status": "failed",
                        "message": str(exc),
                    },
                ) from exc
            except TranslationSemanticFailure as exc:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "translation_semantic_qa_failed",
                        "chapter_id": str(exc.chapter_id),
                        "unit_id": str(exc.unit_id),
                        "unit_index": exc.unit_index,
                        "processed": exc.processed,
                        "failed": 1,
                        "status": "human_review",
                        "issues": [issue.model_dump() for issue in exc.report.issues],
                        "score": exc.report.score,
                    },
                ) from exc
            return TranslationRunResponse(**result.__dict__)
    finally:
        if memory is not None:
            await memory.close()
        if graph is not None:
            await graph.close()
        await engine.dispose()


@app.post(
    "/api/v1/chapters/{chapter_id}/translate",
    response_model=TranslationRunResponse,
    tags=["translation"],
)
async def translate_chapter(chapter_id: UUID) -> TranslationRunResponse:
    return await _run_translation(chapter_id)


@app.post(
    "/api/v1/chapters/{chapter_id}/retry-failed",
    response_model=TranslationRunResponse,
    tags=["translation"],
)
async def retry_failed_translation(chapter_id: UUID) -> TranslationRunResponse:
    return await _run_translation(chapter_id, retry_failed=True)


@app.post(
    "/api/v1/chapters/{chapter_id}/translation-jobs",
    response_model=TranslationJobResponse,
    status_code=202,
    tags=["jobs"],
)
async def create_translation_job(chapter_id: UUID) -> TranslationJobResponse:
    settings = get_settings()
    engine, sessions = session_factory(settings)
    try:
        await create_schema(engine)
        async with sessions() as session:
            chapter = await session.get(Chapter, chapter_id)
            if chapter is None:
                raise HTTPException(status_code=404, detail="chapter not found")
            existing = await session.scalar(
                select(TranslationJob)
                .where(
                    TranslationJob.chapter_id == chapter_id,
                    TranslationJob.status.in_(("queued", "running")),
                )
                .order_by(TranslationJob.created_at.desc())
            )
            if existing is not None:
                if existing.status == "running" and (
                    existing.lease_until is None or existing.lease_until > datetime.now(UTC)
                ):
                    return TranslationJobResponse.model_validate(existing, from_attributes=True)
                existing.status = "queued"
                existing.lease_until = None
                await session.commit()
                job = existing
            else:
                job = TranslationJob(chapter_id=chapter_id)
                session.add(job)
                await session.commit()
                await session.refresh(job)
            from src.workers.translation_task import translation_job_task

            try:
                translation_job_task.delay(str(job.id), str(chapter_id))
            except Exception as exc:
                job.status = "failed"
                job.last_error = f"job dispatch failed: {exc}"
                await session.commit()
                raise HTTPException(status_code=503, detail="job dispatch failed") from exc
            return TranslationJobResponse.model_validate(job, from_attributes=True)
    finally:
        await engine.dispose()


@app.get(
    "/api/v1/jobs/{job_id}",
    response_model=TranslationJobResponse,
    tags=["jobs"],
)
async def get_translation_job(job_id: UUID) -> TranslationJobResponse:
    settings = get_settings()
    engine, sessions = session_factory(settings)
    try:
        await create_schema(engine)
        async with sessions() as session:
            job = await session.get(TranslationJob, job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="job not found")
            return TranslationJobResponse.model_validate(job, from_attributes=True)
    finally:
        await engine.dispose()


@app.post(
    "/api/v1/novels/{novel_id}/translation-jobs",
    response_model=NovelTranslationJobResponse,
    status_code=202,
    tags=["jobs"],
)
async def create_novel_translation_job(novel_id: UUID) -> NovelTranslationJobResponse:
    settings = get_settings()
    engine, sessions = session_factory(settings)
    try:
        await create_schema(engine)
        async with sessions() as session:
            novel = await session.get(Novel, novel_id)
            if novel is None:
                raise HTTPException(status_code=404, detail="novel not found")
            existing = await session.scalar(
                select(NovelTranslationJob)
                .where(
                    NovelTranslationJob.novel_id == novel_id,
                    NovelTranslationJob.status.in_(("queued", "running")),
                )
                .order_by(NovelTranslationJob.created_at.desc())
            )
            if existing is not None:
                return NovelTranslationJobResponse.model_validate(existing, from_attributes=True)
            chapters = (
                await session.scalars(
                    select(Chapter)
                    .options(selectinload(Chapter.units))
                    .where(Chapter.novel_id == novel_id)
                    .order_by(Chapter.chapter_index)
                )
            ).all()
            job = NovelTranslationJob(
                novel_id=novel_id,
                total_chapters=len(chapters),
                total_units=sum(len(chapter.units) for chapter in chapters),
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            from src.workers.translation_task import novel_translation_job_task

            try:
                novel_translation_job_task.delay(str(job.id), str(novel_id))
            except Exception as exc:
                job.status = "failed"
                job.last_error = f"job dispatch failed: {exc}"
                await session.commit()
                raise HTTPException(status_code=503, detail="job dispatch failed") from exc
            return NovelTranslationJobResponse.model_validate(job, from_attributes=True)
    finally:
        await engine.dispose()


@app.get(
    "/api/v1/novel-translation-jobs/{job_id}",
    response_model=NovelTranslationJobResponse,
    tags=["jobs"],
)
async def get_novel_translation_job(job_id: UUID) -> NovelTranslationJobResponse:
    settings = get_settings()
    engine, sessions = session_factory(settings)
    try:
        await create_schema(engine)
        async with sessions() as session:
            job = await session.get(NovelTranslationJob, job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="novel translation job not found")
            return NovelTranslationJobResponse.model_validate(job, from_attributes=True)
    finally:
        await engine.dispose()


@app.get(
    "/api/v1/chapters/{chapter_id}/translations",
    response_model=list[TranslationResponse],
    tags=["translation"],
)
async def list_translations(chapter_id: UUID) -> list[TranslationResponse]:
    engine, sessions = session_factory(get_settings())
    try:
        async with sessions() as session:
            exists = await session.scalar(select(Chapter.id).where(Chapter.id == chapter_id))
            if exists is None:
                raise HTTPException(status_code=404, detail="chapter not found")
            records = (
                await session.scalars(
                    select(Translation)
                    .join(TranslationUnit)
                    .where(TranslationUnit.chapter_id == chapter_id)
                    .order_by(TranslationUnit.source_order, Translation.version)
                )
            ).all()
            return [
                TranslationResponse.model_validate(item, from_attributes=True) for item in records
            ]
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
            source_path = next(
                (
                    chapter.source_text_path
                    for chapter in novel.chapters
                    if chapter.source_text_path
                ),
                None,
            )
            source_epub = (
                await MinioStorage(get_settings()).get(source_path)
                if format == "epub" and source_path
                else None
            )
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
                    ExportChapter(
                        chapter.chapter_index,
                        chapter.title,
                        chapter.source_text,
                        "\n\n".join(
                            translation.translated_text
                            if translation is not None
                            else unit.source_text
                            for unit in sorted(chapter.units, key=lambda item: item.source_order)
                            for translation in [
                                max(unit.translations, key=lambda item: item.version)
                                if unit.translations
                                else None
                            ]
                        )
                        if chapter.units
                        else latest,
                    )
                )
            export = ExportNovel(
                novel.title,
                novel.author,
                novel.source_language,
                novel.target_language,
                tuple(chapters),
                source_epub,
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
