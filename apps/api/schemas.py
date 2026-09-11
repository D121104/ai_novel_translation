from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NovelResponse(BaseModel):
    id: UUID
    title: str
    source_language: str
    target_language: str
    author: str | None
    created_at: datetime


class ChapterResponse(BaseModel):
    id: UUID
    novel_id: UUID
    chapter_index: int
    title: str
    status: str


class Paginated[T](BaseModel):
    items: list[T]
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
