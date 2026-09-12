from uuid import uuid4

import pytest

from src.core.config import Settings
from src.domain.novel.models import Chapter, Translation, TranslationQAResult, TranslationUnit
from src.llm.provider import LLMResponse
from src.qa.semantic import SemanticQAIssue, SemanticQAReport
from src.translation.context import GlossaryTerm
from src.translation.service import TranslationCancelled, TranslationQAFailure, TranslationService


class FakeProvider:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        self.prompts.append(prompt)
        if "Lan has 12 swords." in prompt and "bad" not in prompt:
            return LLMResponse("bad", "fake-model", 1, 1)
        if "Current." in prompt:
            return LLMResponse("Current.", "fake-model", 1, 1)
        return LLMResponse("Lan có 12 kiếm.", "fake-model", 1, 4)


class FailingProvider:
    async def generate(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        if "Lan has 12 swords." in prompt:
            return LLMResponse("", "fake-model", 1, 0)
        return LLMResponse("not a translation", "fake-model", 1, 3)


class ErrorProvider:
    async def generate(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        raise RuntimeError("provider unavailable")


class GoodProvider:
    async def generate(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        text = "Later." if "Later." in prompt else "Lan enters."
        return LLMResponse(text, "fake-model", 1, 2)


class RetryProvider:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        self.prompts.append(prompt)
        if "Second has 12." in prompt:
            return LLMResponse("Mới có 12.", "fake-model", 1, 3)
        return LLMResponse("Ba.", "fake-model", 1, 1)


class FakeSession:
    def __init__(self, chapter: Chapter) -> None:
        self.chapter = chapter
        self.added: list[Translation] = []
        self.qa_results: list[TranslationQAResult] = []
        self.commits = 0

    async def scalar(self, _query):
        return self.chapter

    def add(self, value: Translation | TranslationQAResult) -> None:
        if isinstance(value, Translation):
            self.added.append(value)
            value.unit = next(unit for unit in self.chapter.units if unit.id == value.unit_id)
            value.unit.translations.append(value)
        else:
            self.qa_results.append(value)

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_chapter_translation_processes_pending_units_and_repairs() -> None:
    chapter_id = uuid4()
    unit = TranslationUnit(
        id=uuid4(),
        chapter_id=chapter_id,
        unit_index=0,
        source_order=0,
        source_text="Lan has 12 swords.",
        token_count=4,
        status="pending",
    )
    chapter = Chapter(
        id=chapter_id, chapter_index=1, title="One", source_text="", source_text_path=""
    )
    chapter.units = [unit]
    session = FakeSession(chapter)
    provider = FakeProvider()

    result = await TranslationService(
        session,
        Settings(),
        provider,
        repair_attempts=1,
        names=("Lan",),
        glossary=(GlossaryTerm("swords", "kiếm"),),
    ).translate_chapter(chapter_id)

    assert result.processed == 1
    assert result.status == "completed"
    assert unit.status == "completed"
    assert session.added[0].translated_text == "Lan có 12 kiếm."
    assert len(provider.prompts) == 2
    assert "swords => kiếm" in provider.prompts[1]


@pytest.mark.asyncio
async def test_cancellation_keeps_current_unit_pending_for_resume() -> None:
    chapter_id = uuid4()
    unit = TranslationUnit(
        id=uuid4(),
        chapter_id=chapter_id,
        unit_index=0,
        source_order=0,
        source_text="A paragraph.",
        token_count=2,
        status="pending",
    )
    chapter = Chapter(
        id=chapter_id, chapter_index=1, title="One", source_text="", source_text_path=""
    )
    chapter.units = [unit]

    async def cancel(_unit_id) -> None:
        raise TranslationCancelled()

    with pytest.raises(TranslationCancelled):
        await TranslationService(
            FakeSession(chapter),
            Settings(),
            FailingProvider(),
            on_unit_started=cancel,
        ).translate_chapter(chapter_id)

    assert chapter.status == "paused"
    assert unit.status == "pending"


@pytest.mark.asyncio
async def test_knowledge_extraction_failure_does_not_block_translation(caplog) -> None:
    chapter_id = uuid4()
    unit = TranslationUnit(
        id=uuid4(),
        chapter_id=chapter_id,
        unit_index=0,
        source_order=0,
        source_text="Lan enters.",
        token_count=2,
        status="pending",
    )
    chapter = Chapter(
        id=chapter_id, chapter_index=1, title="One", source_text="", source_text_path=""
    )
    chapter.units = [unit]

    class FailingKnowledgeStage:
        async def prepare_unit(self, **_kwargs) -> None:
            raise TimeoutError("extraction timed out")

    session = FakeSession(chapter)
    result = await TranslationService(
        session,
        Settings(),
        GoodProvider(),
        knowledge_stage=FailingKnowledgeStage(),
    ).translate_chapter(chapter_id)

    assert result.status == "completed"
    assert unit.status == "completed"
    assert session.added[0].translated_text == "Lan enters."
    assert "knowledge extraction failed; continuing translation" in caplog.text


@pytest.mark.asyncio
async def test_semantic_review_keeps_translation_and_allows_later_units() -> None:
    chapter_id = uuid4()
    reviewed = TranslationUnit(
        id=uuid4(),
        chapter_id=chapter_id,
        unit_index=0,
        source_order=0,
        source_text="Lan enters.",
        token_count=2,
        status="pending",
    )
    later = TranslationUnit(
        id=uuid4(),
        chapter_id=chapter_id,
        unit_index=1,
        source_order=1,
        source_text="Later.",
        token_count=1,
        status="pending",
    )
    chapter = Chapter(
        id=chapter_id, chapter_index=1, title="One", source_text="", source_text_path=""
    )
    chapter.units = [reviewed, later]

    class SemanticReviewer:
        def __init__(self) -> None:
            self.calls = 0

        async def run(self, _source, _translation, _context) -> SemanticQAReport:
            self.calls += 1
            if self.calls == 1:
                return SemanticQAReport(
                    passed=False,
                    score=0.94,
                    issues=[SemanticQAIssue(code="TERM_001", message="needs human review")],
                )
            return SemanticQAReport(passed=True, score=1.0)

    session = FakeSession(chapter)
    semantic_qa = SemanticReviewer()
    first = await TranslationService(
        session,
        Settings(),
        GoodProvider(),
        repair_attempts=0,
        semantic_qa=semantic_qa,
    ).translate_chapter(chapter_id)

    assert first.status == "human_review"
    assert first.processed == 2
    assert reviewed.status == "human_review"
    assert later.status == "completed"
    assert [item.translated_text for item in session.added] == ["Lan enters.", "Later."]
    assert any(
        result.stage == "semantic" and result.status == "human_review"
        for result in session.qa_results
    )

    second = await TranslationService(
        session,
        Settings(),
        GoodProvider(),
        repair_attempts=0,
        semantic_qa=semantic_qa,
    ).translate_chapter(chapter_id, retry_failed=True)

    assert second.status == "completed"
    assert reviewed.status == "completed"
    assert sorted({item.version for item in reviewed.translations}) == [1, 2]


@pytest.mark.asyncio
async def test_context_never_contains_later_unit() -> None:
    chapter_id = uuid4()
    first = TranslationUnit(
        id=uuid4(),
        chapter_id=chapter_id,
        unit_index=0,
        source_order=0,
        source_text="Earlier.",
        token_count=1,
        status="completed",
    )
    first.translations = [
        Translation(id=uuid4(), unit_id=first.id, version=1, translated_text="Trước.")
    ]
    second = TranslationUnit(
        id=uuid4(),
        chapter_id=chapter_id,
        unit_index=1,
        source_order=1,
        source_text="Current.",
        token_count=1,
        status="pending",
    )
    later = TranslationUnit(
        id=uuid4(),
        chapter_id=chapter_id,
        unit_index=2,
        source_order=2,
        source_text="FUTURE SECRET.",
        token_count=2,
        status="pending",
    )
    chapter = Chapter(
        id=chapter_id, chapter_index=1, title="One", source_text="", source_text_path=""
    )
    chapter.units = [first, second, later]
    session = FakeSession(chapter)
    provider = FakeProvider()

    await TranslationService(session, Settings(), provider, repair_attempts=0).translate_chapter(
        chapter_id
    )

    assert "FUTURE SECRET" not in provider.prompts[0]
    assert "Trước." in provider.prompts[0]


@pytest.mark.asyncio
async def test_qa_failure_preserves_completed_units_and_leaves_later_pending() -> None:
    chapter_id = uuid4()
    first = TranslationUnit(
        id=uuid4(),
        chapter_id=chapter_id,
        unit_index=0,
        source_order=0,
        source_text="First.",
        token_count=1,
        status="pending",
    )
    failed = TranslationUnit(
        id=uuid4(),
        chapter_id=chapter_id,
        unit_index=1,
        source_order=1,
        source_text="Lan has 12 swords.",
        token_count=4,
        status="pending",
    )
    later = TranslationUnit(
        id=uuid4(),
        chapter_id=chapter_id,
        unit_index=2,
        source_order=2,
        source_text="Later.",
        token_count=1,
        status="pending",
    )
    chapter = Chapter(
        id=chapter_id, chapter_index=1, title="One", source_text="", source_text_path=""
    )
    chapter.units = [first, failed, later]

    with pytest.raises(TranslationQAFailure) as caught:
        await TranslationService(
            FakeSession(chapter), Settings(), FailingProvider(), repair_attempts=0
        ).translate_chapter(chapter_id)

    assert caught.value.processed == 1
    assert "empty" in {issue.code for issue in caught.value.report.issues}
    assert first.status == "completed"
    assert failed.status == "failed"
    assert later.status == "pending"


@pytest.mark.asyncio
async def test_retry_failed_units_preserves_completed_versions_and_order() -> None:
    chapter_id = uuid4()
    first = TranslationUnit(
        id=uuid4(),
        chapter_id=chapter_id,
        unit_index=0,
        source_order=0,
        source_text="First.",
        token_count=1,
        status="completed",
    )
    first.translations = [
        Translation(id=uuid4(), unit_id=first.id, version=1, translated_text="Trước.")
    ]
    failed = TranslationUnit(
        id=uuid4(),
        chapter_id=chapter_id,
        unit_index=1,
        source_order=1,
        source_text="Second has 12.",
        token_count=3,
        status="failed",
    )
    failed.translations = [
        Translation(id=uuid4(), unit_id=failed.id, version=1, translated_text="Cũ có 12.")
    ]
    later = TranslationUnit(
        id=uuid4(),
        chapter_id=chapter_id,
        unit_index=2,
        source_order=2,
        source_text="Third.",
        token_count=1,
        status="pending",
    )
    chapter = Chapter(
        id=chapter_id, chapter_index=1, title="One", source_text="", source_text_path=""
    )
    chapter.units = [first, failed, later]
    provider = RetryProvider()

    result = await TranslationService(
        FakeSession(chapter), Settings(), provider, repair_attempts=0
    ).translate_chapter(chapter_id, retry_failed=True)

    assert result.status == "completed"
    assert result.processed == 2
    assert first.status == "completed"
    assert first.translations[0].translated_text == "Trước."
    assert failed.status == "completed"
    assert max(failed.translations, key=lambda item: item.version).version == 2
    assert later.status == "completed"
    assert "Trước." in provider.prompts[0]
    assert "Third." not in provider.prompts[0]
    assert "Mới có 12." in provider.prompts[1]


@pytest.mark.asyncio
async def test_provider_failure_does_not_leave_unit_translating() -> None:
    chapter_id = uuid4()
    unit = TranslationUnit(
        id=uuid4(),
        chapter_id=chapter_id,
        unit_index=0,
        source_order=0,
        source_text="Source.",
        token_count=1,
        status="pending",
    )
    chapter = Chapter(
        id=chapter_id, chapter_index=1, title="One", source_text="", source_text_path=""
    )
    chapter.units = [unit]

    with pytest.raises(RuntimeError, match="provider unavailable"):
        await TranslationService(
            FakeSession(chapter), Settings(), ErrorProvider()
        ).translate_chapter(chapter_id)

    assert unit.status == "failed"
    assert chapter.status == "failed"
