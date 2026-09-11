# Phase 04 — Knowledge Extraction


Goal: extract entity, alias, fact, relation, event, terminology.

Rules:
- output bắt buộc Pydantic structured schema
- evidence gắn TranslationUnit
- model không ghi DB trực tiếp

DoD:
- sample chapter tạo được structured candidates + evidence


## Exit Gate

Không bắt đầu phase tiếp theo cho đến khi:
- automated tests liên quan pass
- documentation cập nhật
- migration/config reproducible
- không có known blocker severity cao
