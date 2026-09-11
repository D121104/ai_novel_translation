# AI Novel Translation Studio

Foundation (Phase 0) của ứng dụng dịch tiểu thuyết cá nhân.

## Chạy local

Yêu cầu Python 3.12, `uv`, và Docker Desktop.

```bash
Copy-Item .env.example .env
uv sync
docker compose up -d
uv run uvicorn apps.api.main:app --reload
```

Kiểm tra:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Import nhanh một file TXT/JSON/EPUB bằng raw request body:

```bash
curl --data-binary "@book.txt" "http://localhost:8000/imports?filename=book.txt"
```

File gốc được lưu trong MinIO; novel và chapter được lưu trong PostgreSQL.
Import lại cùng nội dung sẽ trả cùng `novel_id` và `idempotent: true`.

`/health` không phụ thuộc hạ tầng. `/ready` kiểm tra PostgreSQL, Neo4j,
Qdrant, Redis và MinIO; nếu một dịch vụ tắt, endpoint trả HTTP 503 và nêu
dịch vụ lỗi.

Quality gates:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy apps src
```

Chạy UI:

```bash
cd frontend
npm install
npm run dev
```

UI mặc định gọi API tại `http://localhost:8000`; có thể đổi bằng
`VITE_API_URL`.

Các volume Docker là named volumes và không bị xóa bởi lệnh khởi động.

## Phạm vi hiện tại

Phase 1 bổ sung parser TXT/JSON/EPUB, phát hiện chapter, lưu file gốc vào
MinIO và lưu Novel/Chapter vào PostgreSQL. Phase 2 bổ sung chunking
 deterministic thành TranslationUnit theo paragraph/sentence boundary. Phase 3
 bổ sung abstraction LLM cho Ollama/OpenAI-compatible, structured output,
 retry/timeout, token accounting và response cache. Phase 4 bổ sung knowledge
 extraction candidates có Pydantic validation và evidence bắt buộc gắn với
 TranslationUnit; extractor chỉ trả proposal, không ghi DB. Retrieval, workers
 và UI sẽ được triển khai ở các phase sau. Phase 5 bổ sung entity resolution
 theo exact alias, normalized/fuzzy matching và ngưỡng an toàn, không tự merge
 candidate confidence thấp hoặc ambiguous. Phase 6 bổ sung Neo4j temporal graph
 synchronization và truy vấn relationship có `as_of_order`, chặn future state.
 Phase 7 bổ sung Qdrant collections cho chunks, translation memory và summaries,
 deterministic embeddings, sparse terms, hybrid fusion và temporal payload filter.
 Phase 8 bổ sung hierarchy summary chapter/arc/volume/world bible, gồm narrative
 và structured facts, với truy vấn bounded và loại bỏ summary tương lai.
 Phase 9 bổ sung GraphRAG orchestration kết hợp graph expansion, Qdrant vectors,
 summaries, lexical reranking, context budget và temporal filtering.
 Phase 10 bổ sung translation context theo priority, locked glossary, addressing
 rules và lưu output versioned qua TranslationStore.
 Phase 11 bổ sung deterministic QA cho empty output, paragraph, number, name,
 glossary, markup và length anomaly, cùng repair loop có history.
 Phase 12 bổ sung Celery/Redis configuration và resumable worker với checkpoint,
 retry và idempotency key.
 Phase 13 bổ sung API versioned `/api/v1/novels` và chapter pagination với
 Pydantic response validation, cùng endpoint import hiện có.
 Phase 14 bổ sung React/Vite management UI cho library, import novel và chapter
 browsing.

## Kilo project configuration

Bộ này dành cho project **AI Novel Translation Studio** cá nhân.

Mục tiêu:
- ít agent;
- phân vai rõ;
- không over-engineering;
- kiểm soát chi phí;
- không để agent tự spawn lung tung;
- giữ đúng Temporal Knowledge + PostgreSQL/Neo4j/Qdrant architecture.

## Agents

```text
novel-engineer            PRIMARY
├── knowledge-engineer    SUBAGENT
├── translation-engineer  SUBAGENT
└── reviewer              SUBAGENT
```

### novel-engineer
Agent chính để bạn giao Phase/task.

Nó có thể:
- đọc/sửa project;
- chạy test;
- gọi đúng 3 subagent;
- điều phối implementation.

Nó không được:
- gọi agent bất kỳ ngoài allowlist;
- dùng Agent Manager;
- tự chạy lệnh phá dữ liệu.

### knowledge-engineer
Chuyên:
- PostgreSQL
- Neo4j
- Qdrant
- entity/alias/identity
- temporal knowledge
- GraphRAG/retrieval

### translation-engineer
Chuyên:
- translation pipeline
- context builder
- prompt
- glossary
- pronoun/addressing
- model routing
- QA/repair
- translation memory

### reviewer
Read-only reviewer:
- xem diff;
- chạy test/lint/type-check;
- tìm bug/regression;
- không sửa file.

## Rules

```text
.kilo/rules/
├── 00-project-scope.md
├── 10-architecture.md
├── 20-coding.md
├── 30-testing.md
├── 40-agent-workflow.md
└── 50-translation-quality.md
```

## Cài đặt

Copy:
- `.kilo/agents/`
- `.kilo/rules/`
- `AGENTS.md`

vào root project.

Sau đó merge phần `instructions` từ `kilo.jsonc.example` vào `kilo.jsonc`
hiện tại của bạn. **Không ghi đè provider/model config đang dùng.**

Ví dụ:

```jsonc
{
  "$schema": "https://app.kilo.ai/config.json",
  "instructions": [
    "AGENTS.md",
    ".kilo/rules/*.md"
  ]
}
```

Kilo tự phát hiện agent Markdown trong `.kilo/agents/`.

Sau khi copy:
- mở session mới; hoặc
- reload Kilo nếu client của bạn hỗ trợ reload.

## Cách dùng

Task bình thường:

```text
@novel-engineer Implement Phase 5 according to PLAN.md.
```

Task knowledge riêng:

```text
@knowledge-engineer Review entity resolution and temporal knowledge implementation.
```

Task translation:

```text
@translation-engineer Improve context building and translation QA without changing the knowledge schema.
```

Review:

```text
@reviewer Review the current diff and run the relevant quality gates. Do not edit files.
```

## Model

Các agent không pin model cứng để không phá config 9router hiện tại.

Gợi ý:
- `novel-engineer`: Luna High/Max Fast khi task khó; Medium/High cho task thường.
- `knowledge-engineer`: Luna High cho GraphRAG/entity resolution khó.
- `translation-engineer`: Luna Medium/High.
- `reviewer`: Luna Medium.

Không cần Sol cho workflow phát triển project cá nhân này.
