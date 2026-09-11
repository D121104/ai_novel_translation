# Phase 12 — Workers Resume


Goal: durable background processing.

Implement:
- Celery
- Redis queues
- idempotency
- checkpoint
- retry
- resume

DoD:
- kill worker rồi restart vẫn tiếp tục đúng vị trí


## Exit Gate

Không bắt đầu phase tiếp theo cho đến khi:
- automated tests liên quan pass
- documentation cập nhật
- migration/config reproducible
- không có known blocker severity cao
