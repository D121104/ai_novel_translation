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

    async def run_translation(_chapter_id, *, retry_failed, job_id: UUID):
        assert _chapter_id == chapter_id
        assert retry_failed is False
        assert job_id == expected_job_id
        return SimpleNamespace(status="completed", processed=2, failed=0)

    monkeypatch.setattr(translation_task, "_set_job", set_job)
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
