from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
        CREATE INDEX IF NOT EXISTS ix_chapters_novel_status ON chapters (novel_id, status);
        CREATE INDEX IF NOT EXISTS ix_translation_units_chapter_status
            ON translation_units (chapter_id, status);
        CREATE INDEX IF NOT EXISTS ix_translation_units_source_order
            ON translation_units (chapter_id, source_order);
        """,
    ),
)


async def apply_migrations(engine: AsyncEngine) -> None:
    """Apply idempotent SQL migrations in order, recording each version."""
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
        )
        for version, statement in MIGRATIONS:
            applied = await connection.scalar(
                text("SELECT 1 FROM schema_migrations WHERE version = :version"),
                {"version": version},
            )
            if applied is None:
                for command in statement.split(";"):
                    if command.strip():
                        await connection.execute(text(command))
                await connection.execute(
                    text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                    {"version": version},
                )
