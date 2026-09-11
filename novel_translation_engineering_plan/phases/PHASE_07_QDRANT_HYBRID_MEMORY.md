# Phase 07 — Qdrant Hybrid Memory


Goal: dense+sparse semantic memory.

Collections:
- novel_chunks
- translation_memory
- story_summaries

Implement:
- embeddings
- sparse representation
- payload indexes
- temporal filter
- hybrid fusion

DoD:
- retrieval không trả future chapter


## Exit Gate

Không bắt đầu phase tiếp theo cho đến khi:
- automated tests liên quan pass
- documentation cập nhật
- migration/config reproducible
- không có known blocker severity cao
