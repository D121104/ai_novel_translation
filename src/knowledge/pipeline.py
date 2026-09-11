from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.novel.models import Entity, KnowledgeProposalRecord
from src.entity_resolution.resolver import CanonicalEntity, EntityResolver, normalize_name
from src.infrastructure.neo4j.temporal_graph import TemporalGraph
from src.knowledge.extractor import KnowledgeExtractor
from src.knowledge.schemas import ExtractionProposal
from src.knowledge.temporal import TemporalRelation


class UnitKnowledgeStage(Protocol):
    async def prepare_unit(
        self,
        *,
        novel_id: UUID,
        chapter_id: UUID,
        unit_id: UUID,
        source_order: int,
        source_text: str,
    ) -> ExtractionProposal: ...


class PostgresKnowledgeStage:
    """Validate and persist model proposals before any graph synchronization."""

    def __init__(
        self,
        session: AsyncSession,
        extractor: KnowledgeExtractor,
        graph: TemporalGraph | None = None,
    ) -> None:
        self._session = session
        self._extractor = extractor
        self._graph = graph

    async def prepare_unit(
        self,
        *,
        novel_id: UUID,
        chapter_id: UUID,
        unit_id: UUID,
        source_order: int,
        source_text: str,
    ) -> ExtractionProposal:
        result = await self._extractor.extract(str(unit_id), source_order, source_text)
        existing = await self._session.scalar(
            select(KnowledgeProposalRecord).where(KnowledgeProposalRecord.unit_id == unit_id)
        )
        if existing is None:
            self._session.add(
                KnowledgeProposalRecord(
                    novel_id=novel_id,
                    chapter_id=chapter_id,
                    unit_id=unit_id,
                    observed_at_order=source_order,
                    extractor_model=result.response.model,
                    proposal=result.proposal.model_dump(mode="json"),
                )
            )
        else:
            existing.observed_at_order = source_order
            existing.extractor_model = result.response.model
            existing.proposal = result.proposal.model_dump(mode="json")
        await self._session.commit()
        if self._graph is not None:
            await self._sync_accepted_knowledge(
                novel_id, result.proposal, source_order, str(unit_id)
            )
        return result.proposal

    async def _sync_accepted_knowledge(
        self,
        novel_id: UUID,
        proposal: ExtractionProposal,
        source_order: int,
        unit_id: str,
    ) -> None:
        graph = self._graph
        if graph is None:
            return
        records = (
            await self._session.scalars(
                select(Entity)
                .options(selectinload(Entity.aliases))
                .where(
                    Entity.novel_id == novel_id,
                    Entity.first_seen_order <= source_order,
                    Entity.status.in_(("confirmed", "user_confirmed")),
                )
            )
        ).all()
        canonical = [
            CanonicalEntity(
                str(record.id),
                record.canonical_name,
                record.entity_type,
                frozenset(
                    alias.alias
                    for alias in record.aliases
                    if alias.valid_from_order <= source_order
                    and (alias.valid_to_order is None or alias.valid_to_order >= source_order)
                ),
            )
            for record in records
        ]
        resolver = EntityResolver(canonical)
        resolved: dict[str, str] = {}
        for candidate in proposal.entities:
            result = resolver.resolve(candidate)
            if result.auto_merged and result.entity_id is not None:
                resolved[normalize_name(candidate.name)] = result.entity_id
                await graph.sync_node(
                    result.entity_id,
                    "Entity",
                    {
                        "canonical_name": next(
                            item.name for item in canonical if item.entity_id == result.entity_id
                        ),
                        "entity_type": next(
                            item.entity_type
                            for item in canonical
                            if item.entity_id == result.entity_id
                        ),
                    },
                )
        for index, relation in enumerate(proposal.relations):
            subject_id = resolved.get(normalize_name(relation.subject))
            object_id = resolved.get(normalize_name(relation.object))
            if subject_id is None or object_id is None:
                continue
            relation_type = (
                "".join(
                    char if char.isalnum() else "_" for char in relation.relation.upper()
                ).strip("_")
                or "RELATED_TO"
            )
            await graph.sync_relation(
                TemporalRelation(
                    relation_id=f"{unit_id}:relation:{index}",
                    subject_id=subject_id,
                    relation_type=relation_type,
                    object_id=object_id,
                    valid_from_order=source_order,
                    evidence_unit_id=unit_id,
                )
            )
