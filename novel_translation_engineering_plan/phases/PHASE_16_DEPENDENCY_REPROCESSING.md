# Phase 16 — Dependency Reprocessing


Goal: mark translations stale khi knowledge thay đổi.

Track dependencies:
- entity_ids
- fact_ids
- glossary_ids
- memory_ids

DoD:
- sửa glossary chỉ mark/reprocess units bị ảnh hưởng


## Exit Gate

Không bắt đầu phase tiếp theo cho đến khi:
- automated tests liên quan pass
- documentation cập nhật
- migration/config reproducible
- không có known blocker severity cao
