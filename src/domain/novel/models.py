from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
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
    __table_args__ = (UniqueConstraint("novel_id", "chapter_index"),)
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
    __table_args__ = (UniqueConstraint("chapter_id", "unit_index"),)
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    chapter_id: Mapped[UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    unit_index: Mapped[int] = mapped_column(Integer)
    source_order: Mapped[int] = mapped_column(Integer)
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
