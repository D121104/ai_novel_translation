# Phase 00 — Foundation


Goal: tạo skeleton, quality tooling và infrastructure local.

Scope:
- uv Python 3.12
- FastAPI skeleton
- Pydantic Settings
- structured logging
- pytest
- Ruff
- mypy
- pre-commit
- Docker Compose
- PostgreSQL
- Neo4j
- Qdrant
- Redis
- MinIO
- health/readiness endpoints

Out of scope:
- novel schema
- ingestion
- LLM
- GraphRAG
- Celery workflow

Definition of Done:
- docker compose up -d chạy ổn
- /health trả OK
- /ready xác minh 5 dependencies
- pytest pass
- ruff pass
- mypy pass


## Exit Gate

Không bắt đầu phase tiếp theo cho đến khi:
- automated tests liên quan pass
- documentation cập nhật
- migration/config reproducible
- không có known blocker severity cao
