# Phase 02 — Chunking


Goal: chia Chapter thành TranslationUnit deterministic.

Rules:
- không cắt giữa câu nếu tránh được
- ưu tiên paragraph/dialogue/scene boundaries
- target 800–2000 source tokens
- overlap chỉ dùng context, không duplicate translation

DoD:
- same input => same units
- source_order tăng đơn điệu


## Exit Gate

Không bắt đầu phase tiếp theo cho đến khi:
- automated tests liên quan pass
- documentation cập nhật
- migration/config reproducible
- không có known blocker severity cao
