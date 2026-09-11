from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Novel(Base):
    __tablename__ = "novels"
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(500))
    source_language: Mapped[str] = mapped_column(String(20), default="unknown")
    target_language: Mapped[str] = mapped_column(String(20), default="vi")
    author: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    chapters: Mapped[list[Chapter]] = relationship(
        back_populates="novel", cascade="all, delete-orphan"
    )


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("novel_id", "chapter_index"),
        Index("ix_chapters_novel_status", "novel_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"))
    chapter_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    source_text_path: Mapped[str] = mapped_column(String(1000))
    source_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="imported")
    novel: Mapped[Novel] = relationship(back_populates="chapters")
    units: Mapped[list[TranslationUnit]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan"
    )


class TranslationUnit(Base):
    __tablename__ = "translation_units"
    __table_args__ = (
        UniqueConstraint("chapter_id", "unit_index"),
        Index("ix_translation_units_chapter_status", "chapter_id", "status"),
        Index("ix_translation_units_source_order", "chapter_id", "source_order"),
    )
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    unit_index: Mapped[int] = mapped_column(Integer)
    source_order: Mapped[int] = mapped_column(BigInteger)
    source_text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    chapter: Mapped[Chapter] = relationship(back_populates="units")
    translations: Mapped[list[Translation]] = relationship(
        back_populates="unit", cascade="all, delete-orphan"
    )


class Translation(Base):
    __tablename__ = "translations"
    __table_args__ = (UniqueConstraint("unit_id", "version"),)
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("translation_units.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    translated_text: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    unit: Mapped[TranslationUnit] = relationship(back_populates="translations")


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (Index("ix_entities_novel_name", "novel_id", "canonical_name"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"))
    entity_type: Mapped[str] = mapped_column(String(80))
    canonical_name: Mapped[str] = mapped_column(String(500))
    vi_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    first_seen_order: Mapped[int] = mapped_column(BigInteger, default=0)
    last_seen_order: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    confidence: Mapped[float] = mapped_column(default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="candidate")
    aliases: Mapped[list[EntityAlias]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )


class EntityAlias(Base):
    __tablename__ = "entity_aliases"
    __table_args__ = (Index("ix_entity_aliases_entity_alias", "entity_id", "alias"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    entity_id: Mapped[UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    alias: Mapped[str] = mapped_column(String(500))
    normalized_alias: Mapped[str] = mapped_column(String(500))
    valid_from_order: Mapped[int] = mapped_column(BigInteger, default=0)
    valid_to_order: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    confidence: Mapped[float] = mapped_column(default=0.0)
    source_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("translation_units.id", ondelete="SET NULL"), nullable=True
    )
    entity: Mapped[Entity] = relationship(back_populates="aliases")


class GlossaryTermRecord(Base):
    __tablename__ = "glossary_terms"
    __table_args__ = (Index("ix_glossary_terms_novel_source", "novel_id", "source"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(500))
    target: Mapped[str] = mapped_column(String(500))
    term_type: Mapped[str] = mapped_column(String(80), default="term")
    description: Mapped[str] = mapped_column(Text, default="")
    first_seen_order: Mapped[int] = mapped_column(BigInteger, default=0)
    locked: Mapped[bool] = mapped_column(default=False)
    confidence: Mapped[float] = mapped_column(default=0.0)
    created_by: Mapped[str] = mapped_column(String(80), default="model")


class KnowledgeProposalRecord(Base):
    __tablename__ = "knowledge_proposals"
    __table_args__ = (
        Index("ix_knowledge_proposals_unit", "unit_id"),
        UniqueConstraint("unit_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"))
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("translation_units.id", ondelete="CASCADE"))
    observed_at_order: Mapped[int] = mapped_column(BigInteger)
    extractor_model: Mapped[str] = mapped_column(String(200))
    proposal: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TranslationQAResult(Base):
    __tablename__ = "translation_qa_results"
    __table_args__ = (Index("ix_translation_qa_results_unit_version", "unit_id", "version"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("translation_units.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(40))
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(default=0.0)
    status: Mapped[str] = mapped_column(String(30))
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TranslationJob(Base):
    __tablename__ = "translation_jobs"
    __table_args__ = (Index("ix_translation_jobs_chapter_status", "chapter_id", "status"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    pipeline_version: Mapped[str] = mapped_column(String(80), default="1")
    status: Mapped[str] = mapped_column(String(30), default="queued")
    current_unit_id: Mapped[UUID | None] = mapped_column(nullable=True)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NovelTranslationJob(Base):
    __tablename__ = "novel_translation_jobs"
    __table_args__ = (Index("ix_novel_translation_jobs_status", "novel_id", "status"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    current_chapter_id: Mapped[UUID | None] = mapped_column(nullable=True)
    total_chapters: Mapped[int] = mapped_column(Integer, default=0)
    processed_chapters: Mapped[int] = mapped_column(Integer, default=0)
    total_units: Mapped[int] = mapped_column(Integer, default=0)
    processed_units: Mapped[int] = mapped_column(Integer, default=0)
    failed_chapters: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StorySummaryRecord(Base):
    __tablename__ = "story_summaries"
    __table_args__ = (Index("ix_story_summaries_novel_order", "novel_id", "end_order"),)

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"))
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    summary_id: Mapped[str] = mapped_column(String(200), unique=True)
    level: Mapped[str] = mapped_column(String(30))
    narrative: Mapped[str] = mapped_column(Text)
    facts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    start_order: Mapped[int] = mapped_column(BigInteger)
    end_order: Mapped[int] = mapped_column(BigInteger)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    action: Mapped[str] = mapped_column(String(80))
    object_type: Mapped[str] = mapped_column(String(80))
    object_id: Mapped[str] = mapped_column(String(200))
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
