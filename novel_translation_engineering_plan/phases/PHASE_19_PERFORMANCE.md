# Phase 19 — Performance


Goal: optimize sau correctness.

Optimize:
- batch embedding
- caching
- DB indexes
- Qdrant payload indexes
- Neo4j indexes
- connection pooling
- controlled concurrency

DoD:
- benchmark trước/sau


## Exit Gate

Không bắt đầu phase tiếp theo cho đến khi:
- automated tests liên quan pass
- documentation cập nhật
- migration/config reproducible
- không có known blocker severity cao
