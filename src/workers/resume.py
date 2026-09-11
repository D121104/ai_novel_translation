import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

ItemT = TypeVar("ItemT")


class CheckpointStore(Protocol):
    async def load(self, job_id: str) -> set[str]: ...

    async def save(self, job_id: str, item_key: str) -> None: ...


@dataclass
class MemoryCheckpointStore:
    completed: dict[str, set[str]] = field(default_factory=dict)

    async def load(self, job_id: str) -> set[str]:
        return set(self.completed.get(job_id, set()))

    async def save(self, job_id: str, item_key: str) -> None:
        self.completed.setdefault(job_id, set()).add(item_key)


@dataclass(frozen=True)
class WorkerReport:
    job_id: str
    processed: int
    skipped: int
    failed: int


class ResumableWorker:
    def __init__(self, checkpoints: CheckpointStore, *, max_retries: int = 2) -> None:
        self._checkpoints = checkpoints
        self._max_retries = max_retries

    async def run(
        self,
        job_id: str,
        items: Sequence[ItemT],
        key: Callable[[ItemT], str],
        process: Callable[[ItemT], Awaitable[None]],
    ) -> WorkerReport:
        completed = await self._checkpoints.load(job_id)
        processed = skipped = failed = 0
        for item in items:
            item_key = key(item)
            if item_key in completed:
                skipped += 1
                continue
            for attempt in range(self._max_retries + 1):
                try:
                    await process(item)
                    await self._checkpoints.save(job_id, item_key)
                    processed += 1
                    break
                except Exception:
                    if attempt >= self._max_retries:
                        failed += 1
                    else:
                        await asyncio.sleep(0.1 * 2**attempt)
        return WorkerReport(job_id, processed, skipped, failed)
