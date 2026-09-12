# AI Novel Translation Studio

Ứng dụng dịch tiểu thuyết dài chạy local, tập trung vào tính nhất quán bản dịch,
knowledge graph theo thời gian và khả năng tiếp tục sau lỗi.

> Dự án dành cho sử dụng cá nhân. Không bao gồm authentication, multi-tenancy,
> cloud deployment hoặc các thành phần enterprise.

## Tính năng

- Import TXT, JSON và EPUB; chuẩn hóa encoding và tự phát hiện chapter.
- Chunk deterministic thành các `TranslationUnit` theo paragraph/sentence boundary.
- LLM provider abstraction cho Ollama và OpenAI-compatible API.
- Structured knowledge extraction với evidence/provenance.
- Entity resolution an toàn: exact alias, normalized/fuzzy matching và xử lý ambiguous.
- Temporal knowledge graph trên Neo4j với truy vấn `as_of_order`.
- Qdrant semantic memory, sparse terms và hybrid retrieval.
- Hierarchical summaries và temporal GraphRAG context.
- Translation context theo priority, locked glossary và addressing rules.
- Deterministic QA, repair loop và versioned translations.
- Resumable workers với checkpoint, retry và idempotency.
- Review knowledge, stale propagation và targeted reprocessing.
- Export TXT, JSON và EPUB; hỗ trợ bilingual export.
- Evaluation metrics, controlled concurrency, batching, caching và database indexes.
- Local operational safeguards: migrations, health checks, metrics, disk status,
  dead-letter queue và recovery drill.

## Kiến trúc

| Thành phần | Trách nhiệm |
|---|---|
| PostgreSQL | Canonical state: novel, chapter, unit, entity, glossary, translation, QA, jobs |
| Neo4j | Relationship, identity và temporal graph traversal |
| Qdrant | Source chunks, translation memory, summaries và semantic retrieval |
| Redis | Job coordination và Celery broker/backend |
| MinIO | Source/import/export object storage |
| FastAPI | Backend API |
| React + Vite | Local management UI |

Mọi plot-sensitive retrieval đều bị giới hạn bởi story position (`as_of_order`).
LLM chỉ tạo proposal; output phải được parse/validate trước khi persistence.

## Yêu cầu

- Windows/macOS/Linux
- Python 3.12
- [`uv`](https://docs.astral.sh/uv/)
- Docker Desktop và Docker Compose
- Node.js 18+ nếu chạy frontend
- Ollama nếu dùng local model

## Cài đặt và chạy local

Từ thư mục repository:

```powershell
Copy-Item .env.example .env
uv sync
docker compose up -d
```

Để khởi động toàn bộ project bằng một lệnh:

Windows PowerShell:

```powershell
.\scripts\start.ps1
```

Ubuntu:

```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

Hai script khởi động các container hạ tầng, API FastAPI, Celery worker và
frontend Vite. Script Windows mở ba cửa sổ PowerShell; script Ubuntu hiển thị
log chung và dừng các tiến trình con khi nhấn `Ctrl+C`. LLM gateway bên ngoài
(nếu dùng) vẫn phải chạy riêng.

Khởi động backend:

```powershell
uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload
```

Khởi động frontend ở terminal khác:

```powershell
Set-Location frontend
npm install
npm run dev
```

- Backend: <http://localhost:8000>
- Frontend: <http://localhost:5173>
- Swagger UI: <http://localhost:8000/docs>

Các Docker volumes là named volumes và không bị xóa bởi lệnh khởi động.

## Cấu hình LLM

### Ollama

Đây là cấu hình mặc định:

```powershell
ollama pull llama3.2
```

`.env`:

```dotenv
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
LLM_BASE_URL=http://localhost:11434
```

### OpenAI-compatible API / 9router

Ứng dụng cũng có thể gọi 9router hoặc gateway tương thích OpenAI:

```dotenv
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://<router-endpoint>
LLM_API_KEY=<api-key>
LLM_MODEL=<model-name>
ENABLE_SEMANTIC_QA=true
```

Provider gọi endpoint:

```text
<LLM_BASE_URL>/v1/chat/completions
```

Không commit `.env` hoặc API key. `LLM_BASE_URL` không nên chứa sẵn
`/chat/completions`; kiểm tra router để tránh lặp `/v1`.
Đặt `ENABLE_SEMANTIC_QA=false` nếu chỉ muốn chạy translation, repair và
deterministic QA.

## API nhanh

Health checks:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost:8000/metrics
```

Import một file:

```powershell
curl --data-binary "@book.txt" "http://localhost:8000/imports?filename=book.txt"
```

Import lại cùng nội dung là idempotent và trả lại `novel_id` tương ứng.

Các endpoint chính:

- `POST /imports`
- `GET /api/v1/novels`
- `GET /api/v1/novels/{novel_id}/chapters`
- `POST /api/v1/review/actions`
- `POST /api/v1/chapters/{chapter_id}/translate`
- `POST /api/v1/chapters/{chapter_id}/retry-failed`
- `GET /api/v1/chapters/{chapter_id}/translations`
- `GET /api/v1/novels/{novel_id}/export`

Sau khi import, chọn novel trên UI và bấm `Translate` ở chapter cần chạy.
Backend sẽ xử lý các unit đang `pending` theo thứ tự source, chạy QA/repair,
lưu translation version và cập nhật trạng thái chapter. Endpoint hiện chạy
đồng bộ để phù hợp local workflow; Celery chỉ được dùng cho các job dài hạn
đã cấu hình riêng.

Nếu deterministic QA thất bại, API trả `422` cùng mã lỗi và danh sách issue (ví dụ
`untranslated_cjk` hoặc `malformed_markup`) thay vì lỗi server chung. Semantic QA chỉ ghi nhận issue cần người
dùng review; bản dịch vẫn được lưu và các unit tiếp theo vẫn chạy. Chapter có issue
semantic sẽ ở trạng thái `human_review`; nhấn `Retry` hoặc gọi endpoint `retry-failed`
để chạy lại thủ công.

Khi export EPUB từ EPUB gốc, hệ thống giữ nguyên archive assets và XHTML
(bao gồm ảnh, CSS, font, cover, style và vị trí tuyệt đối), chỉ thay text node
của chapter đã có bản dịch. EPUB nguồn được đọc lại từ MinIO theo
`source_text_path`.

Trên Windows, Celery tự dùng `solo` với một worker để tránh lỗi `billiard`
do process pool/spawn. Có thể chạy thủ công bằng:

```powershell
uv run celery -A src.workers.celery_app:celery_app worker --loglevel=INFO --pool=solo --concurrency=1
```

Job đang chạy có thể dừng bằng nút `Stop` hoặc `Stop all`. Worker sẽ dừng ở
ranh giới unit hiện tại; unit chưa hoàn tất vẫn ở trạng thái `pending` để resume.
Novel jobs cũng retry các unit đã lỗi khi resume; nếu một chapter vẫn trả trạng thái
`failed`, nguyên nhân được lưu trong trường `last_error` của novel job.

## Database initialization và migrations

Mặc định, local API không tự khởi tạo toàn bộ infrastructure khi startup.
Để bật schema và migration initialization:

```dotenv
RUN_MIGRATIONS_ON_STARTUP=true
PERFORMANCE_INITIALIZE_ON_STARTUP=true
```

Migration PostgreSQL được version-track trong bảng `schema_migrations`.
Neo4j indexes và Qdrant collections/payload indexes được tạo idempotent khi
`PERFORMANCE_INITIALIZE_ON_STARTUP=true`.

## Backup và recovery drill

Backup/restore chỉ dùng DSN từ environment và không ghi credential vào log:

1. Tạo thư mục backup riêng.
2. Dùng `BackupPlan.postgres_command` để chạy `pg_dump`.
3. Kiểm tra file dump trên database tạm.
4. Dùng `BackupPlan.restore_command` để restore vào database tạm.
5. Kiểm tra số lượng novel, chapter và translation trước khi khôi phục database chính.
6. Sao lưu object files MinIO riêng; không xóa Docker volumes trong quá trình kiểm tra.

## Kiểm thử và quality gates

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy apps src
```

Chạy benchmark local không cần external service:

```powershell
uv run python benchmarks/performance.py
uv run pytest tests/unit/test_performance.py
```

Trạng thái kiểm thử gần nhất: **46 passed, 5 skipped**. Một số integration tests
được skip khi các service Docker tương ứng không khả dụng.

## Cấu trúc repository

```text
apps/api/                         FastAPI application và response schemas
src/domain/                       Domain models
src/ingestion/                    Import và parser
src/chunking/                     Deterministic chunking
src/llm/                          LLM provider abstraction
src/knowledge/                    Knowledge extraction và temporal schemas
src/entity_resolution/            Entity matching/resolution
src/infrastructure/               PostgreSQL, Neo4j, Qdrant, Redis, MinIO
src/retrieval/                    Semantic memory và hybrid retrieval
src/graphrag/                     Temporal GraphRAG orchestration
src/translation/                  Translation context và engine
src/qa/                           Deterministic QA và repair
src/workers/                      Celery/resumable worker
src/reprocessing/                 Dependency/stale planning
src/exporter/                     TXT/JSON/EPUB export
src/evaluation/                   Evaluation metrics
benchmarks/                       Local performance benchmarks
tests/                            Unit và opt-in integration tests
frontend/                         React/Vite management UI
novel_translation_engineering_plan/ Roadmap và phase specifications
```

## Phạm vi và nguyên tắc

- PostgreSQL là canonical structured truth.
- Không để future plot knowledge lọt vào context của story position hiện tại.
- Không auto-merge entity có confidence thấp hoặc ambiguous.
- Không để LLM ghi trực tiếp SQL/Cypher vào canonical state.
- Ưu tiên correctness, consistency, temporal safety và resumability trước performance/UI polish.
