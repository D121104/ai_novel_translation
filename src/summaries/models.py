from enum import StrEnum

from pydantic import BaseModel, Field


class SummaryLevel(StrEnum):
    CHAPTER = "chapter"
    ARC = "arc"
    VOLUME = "volume"
    WORLD_BIBLE = "world_bible"


class StructuredFact(BaseModel):
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object_value: str = Field(min_length=1)


class StorySummary(BaseModel):
    summary_id: str
    level: SummaryLevel
    narrative: str = Field(min_length=1)
    facts: list[StructuredFact] = Field(default_factory=list)
    start_order: int = Field(ge=0)
    end_order: int = Field(ge=0)


class SummaryProposal(BaseModel):
    narrative: str = Field(min_length=1)
    facts: list[StructuredFact] = Field(default_factory=list)


def visible_summaries(
    summaries: list[StorySummary], *, as_of_order: int, limit: int = 20
) -> list[StorySummary]:
    """Return only summaries fully observed at the requested story position."""
    visible = [summary for summary in summaries if summary.end_order <= as_of_order]
    return sorted(visible, key=lambda summary: summary.end_order, reverse=True)[:limit]
