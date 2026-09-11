import pytest

from src.workers.resume import MemoryCheckpointStore, ResumableWorker


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
