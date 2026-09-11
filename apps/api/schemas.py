from datetime import datetime
from typing import Any
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


class ReviewAction(BaseModel):
    action: str = Field(pattern="^(merge|split|confirm|reject|edit|lock)$")
    object_type: str = Field(min_length=1)
    object_id: str = Field(min_length=1)
    before_data: dict[str, Any] | None = None
    after_data: dict[str, Any] | None = None
