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
