from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.core.config import Settings


async def check(settings: Settings) -> bool:
    engine = create_async_engine(
        settings.postgres_dsn,
        pool_pre_ping=True,
        connect_args={"timeout": settings.health_timeout_seconds},
    )
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    finally:
        await engine.dispose()
