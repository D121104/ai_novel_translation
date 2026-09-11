from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import ClassVar, Protocol, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import Settings
from src.domain.novel.models import Chapter, Translation, TranslationQAResult, TranslationUnit
from src.knowledge.pipeline import UnitKnowledgeStage
from src.llm.provider import LLMProvider, create_provider
from src.qa.deterministic import QAReport, deterministic_qa
from src.qa.repair import RepairLoop
from src.qa.semantic import SemanticQA, SemanticQAReport
from src.summaries.store import PostgresSummaryStage
from src.translation.context import GlossaryTerm, TranslationContext
from src.translation.context_builder import ContextBuilder
from src.translation.prompts import PromptBuilder

logger = logging.getLogger(__name__)


class TranslationMemorySink(Protocol):
    async def save_translation(
        self,
        novel_id: str,
        chapter_id: str,
        unit_id: str,
        story_order: int,
        source_text: str,
        translated_text: str,
        version: int,
    ) -> None: ...


@dataclass(frozen=True)
class ChapterTranslationResult:
    chapter_id: UUID
    processed: int
    failed: int
    status: str


class TranslationQAFailure(Exception):
    def __init__(
        self,
        *,
        chapter_id: UUID,
        unit_id: UUID,
        unit_index: int,
        report: QAReport,
        processed: int = 0,
    ) -> None:
        self.chapter_id = chapter_id
        self.unit_id = unit_id
        self.unit_index = unit_index
        self.report = report
        self.processed = processed
        super().__init__(f"translation QA failed: {[issue.code for issue in report.issues]}")


class TranslationOrderBlocked(Exception):
    def __init__(self, *, unit_id: UUID, unit_index: int) -> None:
        self.unit_id = unit_id
        self.unit_index = unit_index
        super().__init__(f"unit {unit_index} is blocked by an earlier incomplete unit")


class TranslationSemanticFailure(Exception):
    def __init__(
        self,
        *,
        chapter_id: UUID,
        unit_id: UUID,
        unit_index: int,
        report: SemanticQAReport,
        processed: int = 0,
    ) -> None:
        self.chapter_id = chapter_id
        self.unit_id = unit_id
        self.unit_index = unit_index
        self.report = report
        self.processed = processed
        super().__init__("translation semantic QA failed")


class TranslationService:
    """Run the smallest resumable, temporal-safe chapter translation workflow."""

    _chapter_locks: ClassVar[dict[UUID, asyncio.Lock]] = {}

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        provider: LLMProvider | None = None,
        *,
        repair_attempts: int = 2,
        names: tuple[str, ...] = (),
        glossary: tuple[GlossaryTerm, ...] = (),
        context_builder: ContextBuilder | None = None,
        prompt_builder: PromptBuilder | None = None,
        memory_sink: TranslationMemorySink | None = None,
        knowledge_stage: UnitKnowledgeStage | None = None,
        semantic_qa: SemanticQA | None = None,
        on_unit_started: Callable[[UUID], Awaitable[None]] | None = None,
        summary_stage: PostgresSummaryStage | None = None,
    ) -> None:
        self._session = session
        self._provider = provider or create_provider(settings)
        self._repair_attempts = repair_attempts
        self._names = names
        self._glossary = glossary
        self._context_builder = context_builder
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._memory_sink = memory_sink
        self._knowledge_stage = knowledge_stage
        self._semantic_qa = semantic_qa
        self._on_unit_started = on_unit_started
        self._summary_stage = summary_stage

    async def translate_chapter(
        self, chapter_id: UUID, *, retry_failed: bool = False
    ) -> ChapterTranslationResult:
        lock = self._chapter_locks.setdefault(chapter_id, asyncio.Lock())
        async with lock:
            return await self._translate_chapter(chapter_id, retry_failed=retry_failed)

    async def _translate_chapter(
        self, chapter_id: UUID, *, retry_failed: bool = False
    ) -> ChapterTranslationResult:
        chapter = await self._load_chapter(chapter_id)
        if chapter is None:
            raise LookupError("chapter not found")

        if retry_failed:
            for unit in chapter.units:
                if unit.status in {"failed", "translating"}:
                    unit.status = "pending"

        pending = sorted(
            (unit for unit in chapter.units if unit.status == "pending"),
            key=lambda unit: (unit.source_order, unit.unit_index),
        )
        chapter.status = "translating"
        await self._session.commit()
        processed = 0
        try:
            for unit in pending:
                if any(
                    earlier.status != "completed"
                    for earlier in chapter.units
                    if (earlier.source_order, earlier.unit_index)
                    < (unit.source_order, unit.unit_index)
                ):
                    raise TranslationOrderBlocked(unit_id=unit.id, unit_index=unit.unit_index)
                await self._translate_unit(chapter, unit)
                processed += 1
            chapter.status = (
                "completed"
                if all(unit.status == "completed" for unit in chapter.units)
                else "failed"
            )
            await self._session.commit()
            if chapter.status == "completed" and self._summary_stage is not None:
                await self._summary_stage.finalize(chapter)
        except TranslationQAFailure as exc:
            chapter.status = "failed"
            await self._session.commit()
            raise TranslationQAFailure(
                chapter_id=exc.chapter_id,
                unit_id=exc.unit_id,
                unit_index=exc.unit_index,
                report=exc.report,
                processed=processed,
            ) from exc
        except TranslationSemanticFailure as exc:
            chapter.status = "failed"
            await self._session.commit()
            raise TranslationSemanticFailure(
                chapter_id=exc.chapter_id,
                unit_id=exc.unit_id,
                unit_index=exc.unit_index,
                report=exc.report,
                processed=processed,
            ) from exc
        except Exception:
            chapter.status = "failed"
            await self._session.commit()
            raise
        return ChapterTranslationResult(
            chapter_id,
            processed,
            sum(unit.status == "failed" for unit in chapter.units),
            chapter.status,
        )

    async def _load_chapter(self, chapter_id: UUID) -> Chapter | None:
        return cast(
            Chapter | None,
            await self._session.scalar(
                select(Chapter)
                .options(selectinload(Chapter.units).selectinload(TranslationUnit.translations))
                .where(Chapter.id == chapter_id)
            ),
        )

    async def _translate_unit(self, chapter: Chapter, unit: TranslationUnit) -> None:
        # Only translations from earlier source order are allowed into context.
        previous = ""
        earlier = [
            item
            for item in chapter.units
            if (item.source_order, item.unit_index) < (unit.source_order, unit.unit_index)
        ]
        if earlier:
            prior = max(earlier, key=lambda item: (item.source_order, item.unit_index))
            prior_versions = list(prior.translations)
            if prior_versions:
                previous = max(prior_versions, key=lambda item: item.version).translated_text

        unit.status = "translating"
        await self._session.commit()
        try:
            if self._on_unit_started is not None:
                await self._on_unit_started(unit.id)
            if self._knowledge_stage is not None:
                await self._knowledge_stage.prepare_unit(
                    novel_id=chapter.novel_id,
                    chapter_id=chapter.id,
                    unit_id=unit.id,
                    source_order=unit.source_order,
                    source_text=unit.source_text,
                )
            if self._context_builder is None:
                context = TranslationContext(
                    source=unit.source_text,
                    names=self._names,
                    glossary=self._glossary,
                    previous=previous,
                )
            else:
                context = await self._context_builder.build(
                    novel_id=chapter.novel_id,
                    unit=unit,
                    as_of_order=unit.source_order,
                    previous=previous,
                )
            prompt = self._prompt_builder.build(context)
            response = await self._provider.generate(prompt)
            text = response.text.strip()
            repaired, _history = await RepairLoop(
                self._provider, max_attempts=self._repair_attempts
            ).run(
                unit.source_text,
                text,
                names=context.names,
                glossary=context.glossary,
            )
            report = deterministic_qa(
                unit.source_text,
                repaired,
                names=context.names,
                glossary=context.glossary,
            )
            next_version = max((item.version for item in unit.translations), default=0) + 1
            if not report.passed:
                self._session.add(
                    TranslationQAResult(
                        unit_id=unit.id,
                        version=next_version,
                        stage="deterministic",
                        attempt=self._repair_attempts,
                        score=report.score,
                        status="failed",
                        issues=[issue.__dict__ for issue in report.issues],
                        model=response.model,
                    )
                )
                raise TranslationQAFailure(
                    chapter_id=chapter.id,
                    unit_id=unit.id,
                    unit_index=unit.unit_index,
                    report=report,
                )
            semantic_report = None
            if self._semantic_qa is not None:
                semantic_report = await self._semantic_qa.run(unit.source_text, repaired, context)
                if not semantic_report.passed:
                    self._session.add(
                        TranslationQAResult(
                            unit_id=unit.id,
                            version=next_version,
                            stage="semantic",
                            attempt=0,
                            score=semantic_report.score,
                            status="human_review",
                            issues=[issue.model_dump() for issue in semantic_report.issues],
                            model=response.model,
                        )
                    )
                    raise TranslationSemanticFailure(
                        chapter_id=chapter.id,
                        unit_id=unit.id,
                        unit_index=unit.unit_index,
                        report=semantic_report,
                    )
            self._session.add(
                TranslationQAResult(
                    unit_id=unit.id,
                    version=next_version,
                    stage="deterministic",
                    attempt=self._repair_attempts,
                    score=report.score,
                    status="passed",
                    issues=[issue.__dict__ for issue in report.issues],
                    model=response.model,
                )
            )
            if semantic_report is not None:
                self._session.add(
                    TranslationQAResult(
                        unit_id=unit.id,
                        version=next_version,
                        stage="semantic",
                        attempt=0,
                        score=semantic_report.score,
                        status="passed",
                        issues=[issue.model_dump() for issue in semantic_report.issues],
                        model=response.model,
                    )
                )
            self._session.add(
                Translation(
                    unit_id=unit.id,
                    version=next_version,
                    translated_text=repaired,
                    model=response.model,
                )
            )
            unit.status = "completed"
            await self._session.commit()
            if self._memory_sink is not None:
                try:
                    await self._memory_sink.save_translation(
                        str(chapter.novel_id),
                        str(chapter.id),
                        str(unit.id),
                        unit.source_order,
                        unit.source_text,
                        repaired,
                        next_version,
                    )
                except Exception:
                    # PostgreSQL remains canonical; a memory outage must not turn
                    # an already committed translation into a failed unit.
                    logger.warning("translation memory indexing failed for unit %s", unit.id)
        except Exception:
            unit.status = "failed"
            await self._session.commit()
            raise
