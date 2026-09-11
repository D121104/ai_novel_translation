# AI Novel Translation Studio — Engineering Plan Bundle

Bộ tài liệu này là specification để triển khai một hệ thống dịch tiểu thuyết dài bằng Python,
kết hợp PostgreSQL + Neo4j + Qdrant + Redis + MinIO + LLM.

## Mục tiêu chính

- Dịch truyện dài theo chapter/unit.
- Giữ nhất quán tên riêng, thuật ngữ, xưng hô và phong cách.
- Theo dõi alias, identity, địa điểm, tổ chức, vật phẩm, kỹ năng, sự kiện.
- Lưu quan hệ nhân vật theo thời gian bằng Temporal Knowledge Graph.
- Không để chapter hiện tại nhìn thấy plot tương lai.
- Hybrid retrieval bằng Qdrant + GraphRAG bằng Neo4j.
- Có checkpoint, retry, resume, QA và reprocessing.
- Có thể chạy local trước, mở rộng production sau.

## Thứ tự đọc

1. `PLAN.md`
2. `docs/architecture/01_system_architecture.md`
3. `docs/architecture/02_data_model.md`
4. `docs/architecture/03_temporal_knowledge.md`
5. `docs/architecture/04_retrieval_graphrag.md`
6. `docs/architecture/05_translation_qa.md`
7. `docs/architecture/06_worker_resume.md`
8. `phases/PHASE_00_FOUNDATION.md`
9. Các phase tiếp theo theo thứ tự số.

## Phase 0

Bộ Phase 0 có sẵn trong `phase0/`:

- `CHECKLIST.md`
- `FOLDER_STRUCTURE.md`
- `KILO_PHASE0_PROMPT.md`
- `.env.example`
- `docker-compose.yml`
- `pyproject.toml`

## Quality gate

Không chuyển phase khi Definition of Done của phase trước chưa đạt.

Ưu tiên:

Correctness → Consistency → Retrieval quality → Translation quality → Resilience → Speed → UI
