import asyncio

import pytest

from src.core.performance import AsyncTTLCache, benchmark_async, gather_limited


def test_ttl_cache_reuses_values_and_has_bounded_size() -> None:
    cache = AsyncTTLCache(ttl_seconds=10, max_size=1)
    cache.set("a", 1)
    assert cache.get("a") == 1
    cache.set("b", 2)
    assert cache.get("a") is None
    assert cache.get("b") == 2


@pytest.mark.asyncio
async def test_gather_limited_never_exceeds_concurrency_limit() -> None:
    active = 0
    peak = 0
    lock = asyncio.Lock()

    async def operation(value: int) -> int:
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0)
        async with lock:
            active -= 1
        return value * 2

    assert await gather_limited(range(8), operation, limit=2) == list(range(0, 16, 2))
    assert peak == 2


@pytest.mark.asyncio
async def test_benchmark_reports_iterations_and_rate() -> None:
    result = await benchmark_async("noop", lambda: asyncio.sleep(0), iterations=3)
    assert result.iterations == 3
    assert result.elapsed_seconds >= 0
    assert result.operations_per_second > 0
