# Phase 01 — Ingestion


Goal: import TXT/EPUB/JSON và tạo Novel/Chapter.

Tasks:
- encoding normalization
- parsers
- chapter detector
- MinIO original storage
- Chapter persistence
- import report

DoD:
- import được sample novel
- chapter order đúng
- re-import idempotent


## Exit Gate

Không bắt đầu phase tiếp theo cho đến khi:
- automated tests liên quan pass
- documentation cập nhật
- migration/config reproducible
- không có known blocker severity cao
