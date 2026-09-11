"""Small, dependency-free performance primitives used by bounded pipelines."""

import asyncio
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


class AsyncTTLCache:
    """An in-process cache for repeatable, non-canonical reads."""

    def __init__(self, ttl_seconds: float = 300.0, max_size: int = 1024) -> None:
        if ttl_seconds <= 0 or max_size < 1:
            raise ValueError("ttl_seconds must be positive and max_size must be at least one")
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._values: dict[str, tuple[float, object]] = {}

    def get(self, key: str) -> object | None:
        entry = self._values.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at <= time.monotonic():
            self._values.pop(key, None)
            return None
        return value

    def set(self, key: str, value: object) -> None:
        if len(self._values) >= self._max_size and key not in self._values:
            self._values.pop(next(iter(self._values)))
        self._values[key] = (time.monotonic() + self._ttl, value)


async def gather_limited[T](
    items: Iterable[T], operation: Callable[[T], Awaitable[object]], *, limit: int
) -> list[object]:
    """Run independent work with an explicit concurrency ceiling."""
    if limit < 1:
        raise ValueError("limit must be at least one")
    semaphore = asyncio.Semaphore(limit)

    async def bounded(item: T) -> object:
        async with semaphore:
            return await operation(item)

    return list(await asyncio.gather(*(bounded(item) for item in items)))


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    iterations: int
    elapsed_seconds: float
    operations_per_second: float


async def benchmark_async(
    name: str, operation: Callable[[], Awaitable[object]], *, iterations: int = 10
) -> BenchmarkResult:
    """Measure a repeatable async operation without hiding failures."""
    if iterations < 1:
        raise ValueError("iterations must be at least one")
    started = time.perf_counter()
    for _ in range(iterations):
        await operation()
    elapsed = time.perf_counter() - started
    return BenchmarkResult(name, iterations, elapsed, iterations / max(elapsed, 1e-9))
