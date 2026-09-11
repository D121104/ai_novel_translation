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
    (
        2,
        """
        CREATE INDEX IF NOT EXISTS ix_entities_novel_order
            ON entities (novel_id, first_seen_order, status);
        CREATE INDEX IF NOT EXISTS ix_glossary_terms_novel_locked
            ON glossary_terms (novel_id, locked);
        CREATE INDEX IF NOT EXISTS ix_translation_jobs_status
            ON translation_jobs (status, updated_at);
        CREATE INDEX IF NOT EXISTS ix_translation_qa_results_stage_status
            ON translation_qa_results (stage, status);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_proposals_unit
            ON knowledge_proposals (unit_id);
        CREATE INDEX IF NOT EXISTS ix_story_summaries_novel_order
            ON story_summaries (novel_id, end_order);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_novel_translation_jobs_active
            ON novel_translation_jobs (novel_id) WHERE status IN ('queued', 'running');
        """,
    ),
    (
        3,
        """
        ALTER TABLE translation_units ALTER COLUMN source_order TYPE BIGINT;
        ALTER TABLE entities ALTER COLUMN first_seen_order TYPE BIGINT;
        ALTER TABLE entities ALTER COLUMN last_seen_order TYPE BIGINT;
        ALTER TABLE entity_aliases ALTER COLUMN valid_from_order TYPE BIGINT;
        ALTER TABLE entity_aliases ALTER COLUMN valid_to_order TYPE BIGINT;
        ALTER TABLE glossary_terms ALTER COLUMN first_seen_order TYPE BIGINT;
        ALTER TABLE knowledge_proposals ALTER COLUMN observed_at_order TYPE BIGINT;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_translation_jobs_active_chapter
            ON translation_jobs (chapter_id) WHERE status IN ('queued', 'running');
        """,
    ),
    (
        4,
        """
        ALTER TABLE translation_jobs ADD COLUMN IF NOT EXISTS lease_until TIMESTAMPTZ;
        CREATE INDEX IF NOT EXISTS ix_translation_jobs_lease
            ON translation_jobs (status, lease_until);
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
