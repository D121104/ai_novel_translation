# Phase 0 Checklist

## Repository
- [ ] Initialize Git repository
- [ ] Python 3.12
- [ ] Initialize with `uv`
- [ ] Create `.gitignore`
- [ ] Create `.env.example`
- [ ] No secrets committed

## Quality
- [ ] Ruff configured
- [ ] mypy configured
- [ ] pytest configured
- [ ] pre-commit configured
- [ ] CI-ready commands documented

## Application
- [ ] `apps/api/main.py`
- [ ] config module
- [ ] structured logging
- [ ] dependency interfaces
- [ ] `/health`
- [ ] `/ready`

## Infrastructure
- [ ] PostgreSQL
- [ ] Neo4j
- [ ] Qdrant
- [ ] Redis
- [ ] MinIO

## Connectivity
- [ ] API → PostgreSQL
- [ ] API → Neo4j
- [ ] API → Qdrant
- [ ] API → Redis
- [ ] API → MinIO

## Required commands

```bash
uv sync
docker compose up -d
uv run pytest
uv run ruff check .
uv run mypy apps src
uv run uvicorn apps.api.main:app --reload
```

## Acceptance

`GET /health`

```json
{"status":"ok"}
```

`GET /ready`

phải báo trạng thái riêng của:
- postgres
- neo4j
- qdrant
- redis
- minio

Nếu dependency down:
- HTTP 503
- response phải nói dependency nào fail

## Strict scope

Agent KHÔNG được:
- tạo domain model của novel
- viết parser
- viết GraphRAG
- tích hợp LLM
- thêm Celery jobs
- tạo React frontend
