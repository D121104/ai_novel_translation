# Kilo Code Prompt — Implement Phase 0

Bạn đang triển khai **Phase 0 — Foundation** cho project `novel-translator`.

## Mục tiêu

Tạo foundation sạch, testable và reproducible cho hệ thống AI Novel Translation Studio.

## Bắt buộc đọc trước

1. `PLAN.md`
2. `phases/PHASE_00_FOUNDATION.md`
3. `phase0/CHECKLIST.md`
4. `phase0/FOLDER_STRUCTURE.md`
5. `phase0/docker-compose.yml`
6. `phase0/pyproject.toml`
7. `phase0/.env.example`

## Phạm vi được phép

Chỉ triển khai:

- Python 3.12 + uv
- FastAPI skeleton
- config bằng `pydantic-settings`
- structured logging bằng `structlog`
- health/readiness endpoints
- dependency connectivity checks:
  - PostgreSQL
  - Neo4j
  - Qdrant
  - Redis
  - MinIO
- pytest
- Ruff
- mypy
- pre-commit
- Docker Compose
- README hướng dẫn chạy local

## Không được làm

KHÔNG:
- tạo schema domain của Novel/Chapter/Entity
- tạo Alembic migrations cho domain
- viết parser TXT/EPUB/JSON
- viết LLM provider
- viết entity extraction
- viết GraphRAG
- viết translation pipeline
- thêm Celery workflow
- tạo React frontend
- mở rộng sang Phase 1

## Folder structure

Tuân thủ `phase0/FOLDER_STRUCTURE.md`.

Không tạo kiến trúc phức tạp hơn nếu không cần.

## API requirements

### GET /health

Không gọi external dependencies.

Response:

```json
{
  "status": "ok"
}
```

HTTP 200.

### GET /ready

Kiểm tra:
- postgres
- neo4j
- qdrant
- redis
- minio

Success:

```json
{
  "status": "ready",
  "dependencies": {
    "postgres": "ok",
    "neo4j": "ok",
    "qdrant": "ok",
    "redis": "ok",
    "minio": "ok"
  }
}
```

Nếu bất kỳ dependency fail:
- HTTP 503
- response chỉ rõ dependency fail
- không crash app
- có timeout hợp lý

## Configuration

Không hardcode credentials.

Load từ environment.

Có `.env.example`.

Không commit `.env`.

## Logging

Structured logging.

Không log:
- password
- API key
- secret key
- database credential

## Tests

Tối thiểu:

### Unit
- config loads correctly
- `/health`
- readiness aggregation
- dependency failure maps to 503

### Integration
Mỗi infrastructure adapter có một integration health test,
được skip rõ ràng nếu integration environment không bật.

## Quality commands phải pass

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy apps src
uv run pytest
```

## Docker

Dùng file `phase0/docker-compose.yml` làm baseline.

Có persistent named volumes.

Có healthcheck cho cả 5 services.

Không thêm app container trong Phase 0 trừ khi thật sự cần;
local development ưu tiên chạy FastAPI bằng `uvicorn`.

## Error handling

Health adapter phải:
- timeout
- catch connection errors
- trả status object hoặc raise domain-neutral health exception
- không leak secret

## Code quality

- typing strict
- functions nhỏ
- no unnecessary abstraction
- no speculative framework
- no LangChain
- no agent framework
- no global mutable clients nếu lifecycle không quản lý được

Ưu tiên FastAPI lifespan cho client lifecycle nếu cần.

## Sau khi hoàn thành

Chạy toàn bộ validation.

Sau đó trả report:

1. Files created/modified
2. Commands executed
3. Test results
4. Ruff result
5. mypy result
6. Docker service status
7. `/health` result
8. `/ready` result
9. Any deviations from specification
10. Không bắt đầu Phase 1

Nếu có lỗi, sửa đến khi Phase 0 pass hoặc mô tả blocker chính xác.
