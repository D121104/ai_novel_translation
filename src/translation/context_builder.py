from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.novel.models import Entity, GlossaryTermRecord, TranslationUnit
from src.entity_resolution.resolver import normalize_name
from src.graphrag.retriever import GraphRAGRetriever
from src.retrieval.memory import QdrantMemory
from src.translation.context import AddressingRule, GlossaryTerm, TranslationContext


class MetadataSource(Protocol):
    async def glossary(self, novel_id: UUID) -> tuple[GlossaryTerm, ...]: ...

    async def names(self, novel_id: UUID, *, as_of_order: int) -> tuple[str, ...]: ...

    async def addressing(
        self, novel_id: UUID, *, as_of_order: int
    ) -> tuple[AddressingRule, ...]: ...

    async def entity_ids(self, novel_id: UUID, source: str, *, as_of_order: int) -> list[str]: ...


class EmptyMetadataSource:
    async def glossary(self, novel_id: UUID) -> tuple[GlossaryTerm, ...]:
        return ()

    async def names(self, novel_id: UUID, *, as_of_order: int) -> tuple[str, ...]:
        return ()

    async def addressing(self, novel_id: UUID, *, as_of_order: int) -> tuple[AddressingRule, ...]:
        return ()

    async def entity_ids(self, novel_id: UUID, source: str, *, as_of_order: int) -> list[str]:
        return []


class PostgresMetadataSource:
    """Read approved consistency metadata without exposing future plot facts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def glossary(self, novel_id: UUID) -> tuple[GlossaryTerm, ...]:
        records = (
            await self._session.scalars(
                select(GlossaryTermRecord).where(
                    GlossaryTermRecord.novel_id == novel_id,
                    GlossaryTermRecord.locked.is_(True),
                )
            )
        ).all()
        return tuple(GlossaryTerm(record.source, record.target, True) for record in records)

    async def names(self, novel_id: UUID, *, as_of_order: int) -> tuple[str, ...]:
        records = (
            await self._session.scalars(
                select(Entity).where(
                    Entity.novel_id == novel_id,
                    Entity.first_seen_order <= as_of_order,
                    Entity.status.in_(("confirmed", "user_confirmed")),
                )
            )
        ).all()
        return tuple(record.vi_name or record.canonical_name for record in records)

    async def addressing(self, novel_id: UUID, *, as_of_order: int) -> tuple[AddressingRule, ...]:
        return ()

    async def entity_ids(self, novel_id: UUID, source: str, *, as_of_order: int) -> list[str]:
        records = (
            await self._session.scalars(
                select(Entity)
                .options(selectinload(Entity.aliases))
                .where(
                    Entity.novel_id == novel_id,
                    Entity.first_seen_order <= as_of_order,
                    Entity.status.in_(("confirmed", "user_confirmed")),
                )
            )
        ).all()
        normalized_source = normalize_name(source)
        return [
            str(record.id)
            for record in records
            if normalize_name(record.canonical_name) in normalized_source
            or any(
                alias.valid_from_order <= as_of_order
                and (alias.valid_to_order is None or alias.valid_to_order >= as_of_order)
                and normalize_name(alias.alias) in normalized_source
                for alias in record.aliases
            )
        ]


class ContextBuilder(Protocol):
    async def build(
        self,
        *,
        novel_id: UUID,
        unit: TranslationUnit,
        as_of_order: int,
        previous: str,
    ) -> TranslationContext: ...


class RuntimeContextBuilder:
    def __init__(
        self,
        retriever: GraphRAGRetriever,
        metadata: MetadataSource | None = None,
        memory: QdrantMemory | None = None,
    ) -> None:
        self._retriever = retriever
        self._metadata = metadata or EmptyMetadataSource()
        self._memory = memory

    async def build(
        self,
        *,
        novel_id: UUID,
        unit: TranslationUnit,
        as_of_order: int,
        previous: str,
    ) -> TranslationContext:
        if self._memory is not None:
            await self._memory.save_source(
                str(novel_id),
                str(unit.chapter_id),
                str(unit.id),
                as_of_order,
                unit.source_text,
            )
        glossary = await self._metadata.glossary(novel_id)
        names = await self._metadata.names(novel_id, as_of_order=as_of_order)
        addressing = await self._metadata.addressing(novel_id, as_of_order=as_of_order)
        entity_ids = await self._metadata.entity_ids(
            novel_id, unit.source_text, as_of_order=as_of_order
        )
        retrieved = await self._retriever.retrieve(
            unit.source_text,
            entity_ids=entity_ids,
            as_of_order=as_of_order,
            novel_id=str(novel_id),
        )
        return TranslationContext(
            source=unit.source_text,
            glossary=glossary,
            names=names,
            addressing=addressing,
            previous=previous,
            graph_facts=tuple(item.text for item in retrieved.items if item.kind == "graph"),
            memories=tuple(
                item.text
                for item in retrieved.items
                if item.kind in {"vector", "translation_memory", "summary"}
            ),
        )
