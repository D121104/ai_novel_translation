from src.core.config import Settings


def test_settings_load_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "test-app")
    monkeypatch.setenv("POSTGRES_PORT", "55432")
    settings = Settings()
    assert settings.app_name == "test-app"
    assert settings.postgres_port == 55432
    assert "@localhost:55432/novel_translator" in settings.postgres_dsn


def test_settings_can_disable_semantic_qa(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_SEMANTIC_QA", "false")

    assert Settings().enable_semantic_qa is False
