from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from src.core.config import get_settings
from src.domain.novel.models import Chapter, NovelTranslationJob, TranslationJob
from src.infrastructure.postgres.repository import create_schema, session_factory
from src.translation.service import TranslationCancelled
from src.workers.celery_app import celery_app

_CANCELLED_STATUSES = {"cancel_requested", "cancelled"}


async def _set_job(job_id: UUID, **values: object) -> None:
    settings = get_settings()
    engine, sessions = session_factory(settings)
    try:
        await create_schema(engine)
        async with sessions() as session:
            job = await session.get(TranslationJob, job_id)
            if job is not None:
                if job.status in _CANCELLED_STATUSES and values.get("status") != "cancelled":
                    return
                for key, value in values.items():
                    setattr(job, key, value)
                await session.commit()
    finally:
        await engine.dispose()


async def _set_novel_job(job_id: UUID, **values: object) -> None:
    settings = get_settings()
    engine, sessions = session_factory(settings)
    try:
        await create_schema(engine)
        async with sessions() as session:
            job = await session.get(NovelTranslationJob, job_id)
            if job is not None:
                if job.status in _CANCELLED_STATUSES and values.get("status") != "cancelled":
                    return
                for key, value in values.items():
                    setattr(job, key, value)
                await session.commit()
    finally:
        await engine.dispose()


async def _is_job_cancelled(job_id: UUID, *, novel: bool = False) -> bool:
    settings = get_settings()
    engine, sessions = session_factory(settings)
    try:
        await create_schema(engine)
        async with sessions() as session:
            record = (
                await session.get(NovelTranslationJob, job_id)
                if novel
                else await session.get(TranslationJob, job_id)
            )
            return record is not None and record.status in _CANCELLED_STATUSES
    finally:
        await engine.dispose()


async def run_novel_translation_job(job_id: UUID, novel_id: UUID) -> None:
    from apps.api.main import _run_translation

    settings = get_settings()
    if await _is_job_cancelled(job_id, novel=True):
        await _set_novel_job(job_id, status="cancelled", lease_until=None)
        return
    await _set_novel_job(
        job_id,
        status="running",
        last_error=None,
        lease_until=datetime.now(UTC) + timedelta(minutes=settings.translation_lease_minutes),
    )
    engine, sessions = session_factory(settings)
    try:
        await create_schema(engine)
        async with sessions() as session:
            chapters = await session.scalars(
                select(Chapter.id)
                .where(Chapter.novel_id == novel_id)
                .order_by(Chapter.chapter_index)
            )
            chapter_ids = list(chapters.all())
    finally:
        await engine.dispose()
    processed_chapters = 0
    processed_units = 0
    needs_human_review = False
    try:
        for chapter_id in chapter_ids:
            if await _is_job_cancelled(job_id, novel=True):
                raise TranslationCancelled()
            await _set_novel_job(job_id, current_chapter_id=chapter_id)
            result = await _run_translation(
                chapter_id,
                retry_failed=True,
                recover_translating=True,
                novel_job_id=job_id,
            )
            if result.status not in {"completed", "human_review"}:
                await _set_novel_job(
                    job_id,
                    status="failed",
                    failed_chapters=1,
                    last_error=(
                        f"chapter translation returned status={result.status}; "
                        f"chapter_id={chapter_id}; processed={result.processed}; "
                        f"failed={result.failed}"
                    ),
                    lease_until=None,
                )
                return
            needs_human_review = needs_human_review or result.status == "human_review"
            processed_chapters += 1
            processed_units += result.processed
            await _set_novel_job(
                job_id,
                processed_chapters=processed_chapters,
                processed_units=processed_units,
            )
    except TranslationCancelled:
        await _set_novel_job(
            job_id,
            status="cancelled",
            current_chapter_id=None,
            lease_until=None,
        )
        return
    except HTTPException as exc:
        detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
        status = (
            "human_review" if detail.get("code") == "translation_semantic_qa_failed" else "failed"
        )
        await _set_novel_job(
            job_id,
            status=status,
            processed_chapters=processed_chapters,
            processed_units=processed_units,
            failed_chapters=1 if status == "failed" else 0,
            last_error=str(detail or exc),
            lease_until=None,
        )
        return
    except Exception as exc:
        await _set_novel_job(job_id, status="failed", last_error=str(exc), lease_until=None)
        raise
    await _set_novel_job(
        job_id,
        status="human_review" if needs_human_review else "completed",
        current_chapter_id=None,
        lease_until=None,
    )


@celery_app.task(name="translation.run_novel", bind=True, max_retries=2)  # type: ignore[untyped-decorator]
def novel_translation_job_task(task: Any, job_id: str, novel_id: str) -> None:
    try:
        asyncio.run(run_novel_translation_job(UUID(job_id), UUID(novel_id)))
    except Exception as exc:
        raise task.retry(exc=exc, countdown=2**task.request.retries) from exc


async def run_translation_job(job_id: UUID, chapter_id: UUID, retry_failed: bool = False) -> None:
    from apps.api.main import _run_translation

    settings = get_settings()
    if await _is_job_cancelled(job_id):
        await _set_job(job_id, status="cancelled", current_unit_id=None, lease_until=None)
        return
    await _set_job(
        job_id,
        status="running",
        last_error=None,
        lease_until=datetime.now(UTC) + timedelta(minutes=settings.translation_lease_minutes),
    )
    try:
        result = await _run_translation(
            chapter_id,
            retry_failed=retry_failed,
            recover_translating=True,
            job_id=job_id,
        )
    except TranslationCancelled:
        await _set_job(job_id, status="cancelled", current_unit_id=None, lease_until=None)
        return
    except HTTPException as exc:
        detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
        status = (
            "human_review" if detail.get("code") == "translation_semantic_qa_failed" else "failed"
        )  # noqa: E501
        await _set_job(
            job_id,
            status=status,
            processed=detail.get("processed", 0),
            failed=detail.get("failed", 1),
            current_unit_id=None,
            lease_until=None,
            last_error=str(exc.detail),
        )
        if exc.status_code == 422:
            return
        raise
    except Exception as exc:
        await _set_job(job_id, status="failed", lease_until=None, last_error=str(exc))
        raise
    await _set_job(
        job_id,
        status=result.status,
        processed=result.processed,
        failed=result.failed,
        current_unit_id=None,
        lease_until=None,
    )


@celery_app.task(name="translation.run_chapter", bind=True, max_retries=2)  # type: ignore[untyped-decorator]
def translation_job_task(
    task: Any, job_id: str, chapter_id: str, retry_failed: bool = False
) -> None:
    try:
        asyncio.run(run_translation_job(UUID(job_id), UUID(chapter_id), retry_failed))
    except Exception as exc:
        raise task.retry(exc=exc, countdown=2**task.request.retries) from exc
