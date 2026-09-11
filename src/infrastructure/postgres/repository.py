from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.chunking.chunker import chunk_text
from src.core.config import Settings
from src.domain.novel.models import Base, Chapter, Novel, TranslationUnit
from src.ingestion.parser import ParsedNovel
from src.ingestion.service import NovelRepository


class PostgresNovelRepository(NovelRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_source_hash(self, source_hash: str) -> str | None:
        novel = await self._session.scalar(select(Novel).where(Novel.source_hash == source_hash))
        return str(novel.id) if novel else None

    async def save(self, novel: ParsedNovel, source_hash: str, source_path: str) -> str:
        record = Novel(title=novel.title, author=novel.author, source_hash=source_hash)
        record.chapters = []
        for chapter in novel.chapters:
            chapter_record = Chapter(
                chapter_index=chapter.index,
                title=chapter.title,
                source_text=chapter.text,
                source_text_path=source_path,
            )
            chapter_record.units = [
                TranslationUnit(
                    unit_index=unit.unit_index,
                    source_order=unit.source_order,
                    source_text=unit.source_text,
                    token_count=unit.token_count,
                )
                for unit in chunk_text(chapter.text)
            ]
            record.chapters.append(chapter_record)
        self._session.add(record)
        await self._session.commit()
        return str(record.id)


async def create_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


def session_factory(settings: Settings) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(settings.postgres_dsn, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)
