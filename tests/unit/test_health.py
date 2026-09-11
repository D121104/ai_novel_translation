import pytest

from src.infrastructure.health import check_dependencies


async def succeeds() -> bool:
    return True


async def fails() -> bool:
    raise ConnectionError("unavailable")


@pytest.mark.asyncio
async def test_health_aggregation() -> None:
    assert await check_dependencies({"good": succeeds}) == {"good": "ok"}


@pytest.mark.asyncio
async def test_dependency_failure_is_isolated() -> None:
    assert await check_dependencies({"bad": fails, "good": succeeds}) == {
        "bad": "error",
        "good": "ok",
    }
