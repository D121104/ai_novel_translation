import asyncio
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from apps.api.main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_503_when_dependency_fails(monkeypatch) -> None:
    async def unhealthy(_checks):
        return {"postgres": "error", "neo4j": "ok", "qdrant": "ok", "redis": "ok", "minio": "ok"}

    monkeypatch.setattr("apps.api.main.check_dependencies", unhealthy)
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["detail"]["dependencies"]["postgres"] == "error"


def test_start_translation_endpoint_uses_fake_provider(monkeypatch) -> None:
    from types import SimpleNamespace
    from uuid import uuid4

    chapter_id = uuid4()

    class Engine:
        async def dispose(self) -> None:
            pass

    class RuntimeGraph:
        async def close(self) -> None:
            pass

    class RuntimeMemory:
        async def ensure_collections(self) -> None:
            pass

        async def close(self) -> None:
            pass

    class SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args) -> None:
            pass

    class FakeService:
        def __init__(self, _session, _settings, **_kwargs) -> None:
            pass

        async def translate_chapter(self, value):
            assert value == chapter_id
            return SimpleNamespace(chapter_id=value, processed=1, failed=0, status="completed")

    monkeypatch.setattr(
        "apps.api.main.session_factory", lambda _settings: (Engine(), SessionContext)
    )
    monkeypatch.setattr("apps.api.main.TemporalGraph", lambda _settings: RuntimeGraph())
    monkeypatch.setattr("apps.api.main.QdrantMemory", lambda _settings: RuntimeMemory())

    async def fake_create_schema(_engine):
        pass

    monkeypatch.setattr("apps.api.main.create_schema", fake_create_schema)
    monkeypatch.setattr("apps.api.main.TranslationService", FakeService)
    with TestClient(app) as client:
        response = client.post(f"/api/v1/chapters/{chapter_id}/translate")
    assert response.status_code == 200
    assert response.json()["processed"] == 1


def test_translate_endpoint_returns_structured_422_for_qa_failure(monkeypatch) -> None:
    from uuid import uuid4

    from src.qa.deterministic import QAIssue, QAReport
    from src.translation.service import TranslationQAFailure

    chapter_id = uuid4()
    unit_id = uuid4()

    class Engine:
        async def dispose(self) -> None:
            pass

    class RuntimeGraph:
        async def close(self) -> None:
            pass

    class RuntimeMemory:
        async def ensure_collections(self) -> None:
            pass

        async def close(self) -> None:
            pass

    class SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args) -> None:
            pass

    class FakeService:
        def __init__(self, _session, _settings, **_kwargs) -> None:
            pass

        async def translate_chapter(self, value):
            raise TranslationQAFailure(
                chapter_id=value,
                unit_id=unit_id,
                unit_index=4,
                report=QAReport((QAIssue("wrong_number", "numeric values changed"),), 0.85),
                processed=3,
            )

    monkeypatch.setattr(
        "apps.api.main.session_factory", lambda _settings: (Engine(), SessionContext)
    )
    monkeypatch.setattr("apps.api.main.TemporalGraph", lambda _settings: RuntimeGraph())
    monkeypatch.setattr("apps.api.main.QdrantMemory", lambda _settings: RuntimeMemory())

    async def fake_create_schema(_engine):
        pass

    monkeypatch.setattr("apps.api.main.create_schema", fake_create_schema)
    monkeypatch.setattr("apps.api.main.TranslationService", FakeService)
    with TestClient(app) as client:
        response = client.post(f"/api/v1/chapters/{chapter_id}/translate")

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "translation_qa_failed",
        "chapter_id": str(chapter_id),
        "unit_id": str(unit_id),
        "unit_index": 4,
        "processed": 3,
        "failed": 1,
        "status": "failed",
        "issues": [
            {"code": "wrong_number", "message": "numeric values changed", "severity": "error"}
        ],
    }


def test_delete_novel_endpoint_deletes_record(monkeypatch) -> None:
    from uuid import uuid4

    novel_id = uuid4()

    class NovelRecord:
        pass

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            pass

        async def get(self, _model, value):
            assert value == novel_id
            return NovelRecord()

        async def delete(self, value) -> None:
            self.deleted = value

        async def commit(self) -> None:
            pass

    class Engine:
        async def dispose(self) -> None:
            pass

    monkeypatch.setattr(
        "apps.api.main.session_factory", lambda _settings: (Engine(), lambda: Session())
    )
    with TestClient(app) as client:
        response = client.delete(f"/api/v1/novels/{novel_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"


def test_cancel_translation_job_marks_running_job_cancelled(monkeypatch) -> None:
    from uuid import uuid4

    from apps.api.main import cancel_translation_job

    job_id = uuid4()
    chapter_id = uuid4()
    job = type(
        "Job",
        (),
        {
            "id": job_id,
            "chapter_id": chapter_id,
            "pipeline_version": "1",
            "status": "running",
            "current_unit_id": uuid4(),
            "processed": 2,
            "failed": 0,
            "retry_count": 0,
            "last_error": None,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
            "lease_until": datetime.now(UTC),
        },
    )()

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            pass

        async def get(self, _model, value):
            assert value == job_id
            return job

        async def commit(self) -> None:
            pass

    class Engine:
        async def dispose(self) -> None:
            pass

    monkeypatch.setattr(
        "apps.api.main.session_factory", lambda _settings: (Engine(), lambda: Session())
    )

    async def fake_create_schema(_engine):
        pass

    monkeypatch.setattr("apps.api.main.create_schema", fake_create_schema)

    response = asyncio.run(cancel_translation_job(job_id))

    assert response.status == "cancelled"
    assert response.current_unit_id is None
    assert response.lease_until is None
