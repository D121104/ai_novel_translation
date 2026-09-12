import sys
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from src.workers.resume import MemoryCheckpointStore, ResumableWorker


def test_windows_worker_uses_solo_pool() -> None:
    from src.workers.celery_app import celery_app

    if sys.platform == "win32":
        assert celery_app.conf.worker_pool == "solo"
        assert celery_app.conf.worker_concurrency == 1


def test_celery_includes_translation_tasks() -> None:
    from src.workers.celery_app import celery_app

    celery_app.loader.import_default_modules()
    assert "src.workers.translation_task" in celery_app.conf.include
    assert "translation.run_novel" in celery_app.tasks
    assert "translation.run_chapter" in celery_app.tasks


@pytest.mark.asyncio
async def test_worker_resumes_after_failure_without_reprocessing() -> None:
    checkpoints = MemoryCheckpointStore()
    seen: list[int] = []
    worker = ResumableWorker(checkpoints, max_retries=0)

    async def process(item: int) -> None:
        seen.append(item)
        if item == 2 and seen.count(2) == 1:
            raise RuntimeError("worker killed")

    first = await worker.run("job-1", [1, 2, 3], str, process)
    second = await worker.run("job-1", [1, 2, 3], str, process)
    assert first.failed == 1
    assert second.processed == 1 and second.skipped == 2
    assert seen == [1, 2, 3, 2]


@pytest.mark.asyncio
async def test_translation_job_updates_durable_status_and_progress(monkeypatch) -> None:
    from src.workers import translation_task

    expected_job_id = uuid4()
    chapter_id = uuid4()
    updates: list[dict[str, object]] = []

    async def set_job(_job_id, **values):
        updates.append(values)

    async def is_cancelled(_job_id, *, novel=False):
        assert novel is False
        return False

    async def run_translation(_chapter_id, *, retry_failed, recover_translating, job_id: UUID):
        assert _chapter_id == chapter_id
        assert retry_failed is False
        assert recover_translating is True
        assert job_id == expected_job_id
        return SimpleNamespace(status="completed", processed=2, failed=0)

    monkeypatch.setattr(translation_task, "_set_job", set_job)
    monkeypatch.setattr(translation_task, "_is_job_cancelled", is_cancelled)
    monkeypatch.setattr("apps.api.main._run_translation", run_translation)

    await translation_task.run_translation_job(expected_job_id, chapter_id)

    assert updates[0]["status"] == "running"
    assert updates[0]["last_error"] is None
    assert updates[0]["lease_until"] is not None
    assert updates[1] == {
        "status": "completed",
        "processed": 2,
        "failed": 0,
        "current_unit_id": None,
        "lease_until": None,
    }


@pytest.mark.asyncio
async def test_translation_job_stops_without_retrying_when_cancelled(monkeypatch) -> None:
    from src.workers import translation_task

    job_id = uuid4()
    chapter_id = uuid4()
    updates: list[dict[str, object]] = []

    async def set_job(_job_id, **values):
        updates.append(values)

    async def is_cancelled(_job_id, *, novel=False):
        assert novel is False
        return True

    monkeypatch.setattr(translation_task, "_set_job", set_job)
    monkeypatch.setattr(translation_task, "_is_job_cancelled", is_cancelled)

    await translation_task.run_translation_job(job_id, chapter_id)

    assert updates == [{"status": "cancelled", "current_unit_id": None, "lease_until": None}]


@pytest.mark.asyncio
async def test_novel_job_retries_failed_units_and_records_failed_chapter(monkeypatch) -> None:
    from src.workers import translation_task

    job_id = uuid4()
    novel_id = uuid4()
    chapter_ids = [uuid4(), uuid4()]
    updates: list[dict[str, object]] = []
    translated_chapters: list[UUID] = []

    class Engine:
        async def dispose(self) -> None:
            pass

    class Result:
        def all(self) -> list[UUID]:
            return chapter_ids

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            pass

        async def scalars(self, _query):
            return Result()

    async def set_novel_job(_job_id, **values):
        updates.append(values)

    async def is_cancelled(_job_id, *, novel=False):
        assert novel is True
        return False

    async def run_translation(chapter_id, *, retry_failed, recover_translating, novel_job_id):
        assert retry_failed is True
        assert recover_translating is True
        assert novel_job_id == job_id
        translated_chapters.append(chapter_id)
        return SimpleNamespace(status="failed", processed=0, failed=1)

    monkeypatch.setattr(translation_task, "session_factory", lambda _settings: (Engine(), Session))
    monkeypatch.setattr(translation_task, "create_schema", lambda _engine: _noop_async())
    monkeypatch.setattr(translation_task, "_set_novel_job", set_novel_job)
    monkeypatch.setattr(translation_task, "_is_job_cancelled", is_cancelled)
    monkeypatch.setattr("apps.api.main._run_translation", run_translation)

    await translation_task.run_novel_translation_job(job_id, novel_id)

    assert translated_chapters == [chapter_ids[0]]
    assert updates[0]["status"] == "running"
    assert updates[0]["last_error"] is None
    assert updates[-1]["status"] == "failed"
    assert updates[-1]["last_error"] == (
        f"chapter translation returned status=failed; chapter_id={chapter_ids[0]}; "
        "processed=0; failed=1"
    )


@pytest.mark.asyncio
async def test_novel_job_records_deterministic_qa_failure_without_celery_retry(monkeypatch) -> None:
    from fastapi import HTTPException

    from src.workers import translation_task

    job_id = uuid4()
    novel_id = uuid4()
    chapter_id = uuid4()
    updates: list[dict[str, object]] = []

    class Engine:
        async def dispose(self) -> None:
            pass

    class Result:
        def all(self) -> list[UUID]:
            return [chapter_id]

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            pass

        async def scalars(self, _query):
            return Result()

    async def set_novel_job(_job_id, **values):
        updates.append(values)

    async def is_cancelled(_job_id, *, novel=False):
        return False

    async def run_translation(_chapter_id, **_kwargs):
        raise HTTPException(
            status_code=422,
            detail={"code": "translation_qa_failed", "unit_index": 1},
        )

    monkeypatch.setattr(translation_task, "session_factory", lambda _settings: (Engine(), Session))
    monkeypatch.setattr(translation_task, "create_schema", lambda _engine: _noop_async())
    monkeypatch.setattr(translation_task, "_set_novel_job", set_novel_job)
    monkeypatch.setattr(translation_task, "_is_job_cancelled", is_cancelled)
    monkeypatch.setattr("apps.api.main._run_translation", run_translation)

    await translation_task.run_novel_translation_job(job_id, novel_id)

    assert updates[-1]["status"] == "failed"
    assert updates[-1]["failed_chapters"] == 1
    assert "translation_qa_failed" in str(updates[-1]["last_error"])


@pytest.mark.asyncio
async def test_novel_job_continues_after_human_review_chapter(monkeypatch) -> None:
    from src.workers import translation_task

    job_id = uuid4()
    novel_id = uuid4()
    chapter_ids = [uuid4(), uuid4()]
    updates: list[dict[str, object]] = []
    translated_chapters: list[UUID] = []

    class Engine:
        async def dispose(self) -> None:
            pass

    class Result:
        def all(self) -> list[UUID]:
            return chapter_ids

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            pass

        async def scalars(self, _query):
            return Result()

    async def set_novel_job(_job_id, **values):
        updates.append(values)

    async def is_cancelled(_job_id, *, novel=False):
        return False

    async def run_translation(chapter_id, **_kwargs):
        translated_chapters.append(chapter_id)
        status = "human_review" if chapter_id == chapter_ids[0] else "completed"
        return SimpleNamespace(status=status, processed=1, failed=0)

    monkeypatch.setattr(translation_task, "session_factory", lambda _settings: (Engine(), Session))
    monkeypatch.setattr(translation_task, "create_schema", lambda _engine: _noop_async())
    monkeypatch.setattr(translation_task, "_set_novel_job", set_novel_job)
    monkeypatch.setattr(translation_task, "_is_job_cancelled", is_cancelled)
    monkeypatch.setattr("apps.api.main._run_translation", run_translation)

    await translation_task.run_novel_translation_job(job_id, novel_id)

    assert translated_chapters == chapter_ids
    assert updates[-1] == {
        "status": "human_review",
        "current_chapter_id": None,
        "lease_until": None,
    }


async def _noop_async() -> None:
    pass
