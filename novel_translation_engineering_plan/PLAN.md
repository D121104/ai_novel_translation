# PLAN.md — AI Novel Translation Studio

## 1. Product Vision

Xây dựng một nền tảng dịch tiểu thuyết dài có memory lâu dài, knowledge graph,
semantic retrieval và kiểm soát consistency theo thời gian.

Hệ thống phải hỗ trợ:

- 1M–20M+ từ.
- 1,000–10,000+ chapter.
- 100,000+ translation units.
- 10,000+ entities.
- 100,000+ facts/relationships.

## 2. Core Architecture

Frontend:
- React + Vite
- Cytoscape.js cho graph

Backend:
- FastAPI
- Pydantic v2
- SQLAlchemy 2
- Alembic

State:
- PostgreSQL = canonical source of truth
- Neo4j = temporal knowledge graph
- Qdrant = semantic memory / hybrid retrieval
- Redis = job coordination
- MinIO = raw/parsed/exported files

AI:
- LLM provider abstraction
- Ollama
- OpenAI-compatible API
- Dense embeddings
- Sparse retrieval
- Reranker
- QA model

Workers:
- Celery

Tooling:
- Python 3.12
- uv
- pytest
- Ruff
- mypy
- pre-commit
- Docker Compose

## 3. Architectural Principles

### 3.1 PostgreSQL owns canonical state
PostgreSQL giữ:
- Novel/Volume/Arc/Chapter/TranslationUnit
- Entity/EntityAlias
- Fact/FactEvidence
- Glossary
- Translation
- QA result
- Job/checkpoint
- Versioning
- Dependency tracking

### 3.2 Neo4j owns relationship traversal
Neo4j phục vụ:
- character relations
- identity
- organization membership
- location hierarchy
- event participation
- temporal relationship queries
- character-specific knowledge

### 3.3 Qdrant owns semantic memory
Qdrant phục vụ:
- source chunks
- translation memory
- story summaries
- dense retrieval
- sparse retrieval
- hybrid fusion
- payload filtering

### 3.4 Temporal safety is mandatory
Mọi retrieval phải dùng `as_of_order` hoặc tương đương.

Không đưa future plot vào context của chapter hiện tại.

### 3.5 LLM never directly owns canonical truth
LLM chỉ đề xuất:
- entity
- alias
- fact
- relation
- terminology
- event

Pipeline phải validate trước khi persist.

## 4. Development Sequence

1. Phase 0 — Foundation
2. Phase 1 — Ingestion
3. Phase 2 — Chunking
4. Phase 3 — LLM Foundation
5. Phase 4 — Knowledge Extraction
6. Phase 5 — Entity Resolution
7. Phase 6 — Neo4j Temporal Graph
8. Phase 7 — Qdrant Hybrid Memory
9. Phase 8 — Hierarchical Summaries
10. Phase 9 — GraphRAG
11. Phase 10 — Translation Engine
12. Phase 11 — QA / Repair
13. Phase 12 — Workers / Resume
14. Phase 13 — Backend API
15. Phase 14 — React UI
16. Phase 15 — Knowledge Review UI
17. Phase 16 — Dependency / Reprocessing
18. Phase 17 — Export
19. Phase 18 — Evaluation
20. Phase 19 — Performance
21. Phase 20 — Production Hardening

## 5. Milestones

- M0 Infrastructure ready
- M1 Novel imported
- M2 Knowledge extracted
- M3 Entity resolution stable
- M4 Temporal Neo4j graph working
- M5 Qdrant hybrid retrieval working
- M6 GraphRAG working
- M7 First chapter translated end-to-end
- M8 QA + repair working
- M9 One full volume translated
- M10 React management UI
- M11 Full novel translated
- M12 Evaluation + optimization

## 6. Non-goals for early phases

Không làm sớm:
- Multi-user auth
- Cloud deployment
- LangChain abstraction
- Agents tự do thay pipeline deterministic
- Neo4j GDS advanced analytics
- Grafana dashboards
- Auto merge entity confidence thấp
- Parallel translation không kiểm soát

## 7. Definition of Done của toàn project

Hệ thống có thể:
- Import novel
- Detect chapter
- Chunk deterministic
- Extract knowledge
- Resolve aliases
- Build temporal graph
- Build semantic memory
- Build summaries
- Retrieve GraphRAG context
- Translate
- QA
- Resume after crash
- Edit glossary/knowledge
- Mark affected translations stale
- Retranslate
- Export TXT/EPUB/JSON

Khi dịch tại vị trí N, model chỉ được biết knowledge hợp lệ tại N.
