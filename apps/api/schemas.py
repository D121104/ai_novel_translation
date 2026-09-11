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


class TranslationResponse(BaseModel):
    id: UUID
    unit_id: UUID
    version: int
    translated_text: str
    model: str | None


class TranslationRunResponse(BaseModel):
    chapter_id: UUID
    processed: int
    failed: int
    status: str


class QAIssueResponse(BaseModel):
    code: str
    message: str
    severity: str


class TranslationQAFailureResponse(BaseModel):
    code: str
    chapter_id: UUID
    unit_id: UUID
    unit_index: int
    processed: int
    failed: int
    status: str
    issues: list[QAIssueResponse]


class TranslationJobResponse(BaseModel):
    id: UUID
    chapter_id: UUID
    pipeline_version: str
    status: str
    current_unit_id: UUID | None
    processed: int
    failed: int
    retry_count: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    lease_until: datetime | None


class NovelTranslationJobResponse(BaseModel):
    id: UUID
    novel_id: UUID
    status: str
    current_chapter_id: UUID | None
    total_chapters: int
    processed_chapters: int
    total_units: int
    processed_units: int
    failed_chapters: int
    last_error: str | None
    lease_until: datetime | None
    created_at: datetime
    updated_at: datetime


class UnitContentResponse(BaseModel):
    unit_id: UUID
    unit_index: int
    source_text: str
    translated_text: str | None


class ChapterContentResponse(BaseModel):
    id: UUID
    chapter_index: int
    title: str
    source_text: str
    units: list[UnitContentResponse]


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
