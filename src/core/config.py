from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "novel-translator"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    health_timeout_seconds: float = 2.0
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "novel_translator"
    postgres_user: str = "novel"
    postgres_password: SecretStr = SecretStr("novel_dev_password")
    postgres_pool_size: int = 5
    postgres_max_overflow: int = 10
    postgres_pool_timeout_seconds: float = 30.0
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("neo4j_dev_password")
    neo4j_max_connection_pool_size: int = 50
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: SecretStr = SecretStr("minioadmin123")
    minio_secure: bool = False
    minio_bucket: str = "novels"
    llm_provider: str = "ollama"
    llm_model: str = "llama3.2"
    llm_base_url: str = "http://localhost:11434"
    llm_api_key: SecretStr | None = None
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 2
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    performance_cache_ttl_seconds: float = 300.0
    performance_concurrency_limit: int = 4
    performance_initialize_on_startup: bool = False
    run_migrations_on_startup: bool = False
    disk_alert_min_free_bytes: int = 1_073_741_824

    @property
    def postgres_dsn(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password.get_secret_value()}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
