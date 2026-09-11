from collections.abc import Awaitable, Callable

HealthCheck = Callable[[], Awaitable[bool]]


async def check_dependencies(checks: dict[str, HealthCheck]) -> dict[str, str]:
    results: dict[str, str] = {}
    for name, check in checks.items():
        try:
            results[name] = "ok" if await check() else "error"
        except Exception:
            results[name] = "error"
    return results
