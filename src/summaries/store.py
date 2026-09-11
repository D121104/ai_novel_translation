from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.novel.models import Chapter, StorySummaryRecord
from src.retrieval.memory import QdrantMemory
from src.summaries.builder import SummaryBuilder
from src.summaries.models import StorySummary


class PostgresSummaryStage:
    def __init__(
        self,
        session: AsyncSession,
        builder: SummaryBuilder,
        memory: QdrantMemory | None = None,
    ) -> None:
        self._session = session
        self._builder = builder
        self._memory = memory

    async def finalize(self, chapter: Chapter) -> StorySummary:
        ordered_units = sorted(chapter.units, key=lambda unit: unit.source_order)
        start_order = ordered_units[0].source_order if ordered_units else 0
        end_order = ordered_units[-1].source_order if ordered_units else start_order
        summary = await self._builder.build(
            f"chapter:{chapter.id}",
            "chapter",
            chapter.source_text,
            start_order=start_order,
            end_order=end_order,
        )
        record = await self._session.scalar(
            select(StorySummaryRecord).where(StorySummaryRecord.summary_id == summary.summary_id)
        )
        values = {
            "novel_id": chapter.novel_id,
            "chapter_id": chapter.id,
            "summary_id": summary.summary_id,
            "level": summary.level.value,
            "narrative": summary.narrative,
            "facts": [fact.model_dump() for fact in summary.facts],
            "start_order": summary.start_order,
            "end_order": summary.end_order,
        }
        if record is None:
            self._session.add(StorySummaryRecord(**values))
        else:
            for key, value in values.items():
                setattr(record, key, value)
        await self._session.commit()
        if self._memory is not None:
            await self._memory.save_summary(
                str(chapter.novel_id), summary.summary_id, summary.end_order, summary.narrative
            )
        return summary
