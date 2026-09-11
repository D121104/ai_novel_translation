# Phase 09 — Graphrag


Goal: kết hợp Neo4j + Qdrant + SQL.

Flow:
- entity detect
- graph expand
- vector candidates
- temporal filtering
- rerank
- context select

DoD:
- benchmark retrieval đạt Recall@K mục tiêu đã cấu hình


## Exit Gate

Không bắt đầu phase tiếp theo cho đến khi:
- automated tests liên quan pass
- documentation cập nhật
- migration/config reproducible
- không có known blocker severity cao
