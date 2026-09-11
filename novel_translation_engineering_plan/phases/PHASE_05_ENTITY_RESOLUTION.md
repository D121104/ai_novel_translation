# Phase 05 — Entity Resolution


Goal: resolve nhiều mention về canonical entity.

Pipeline:
- exact alias
- normalized match
- fuzzy lexical
- semantic candidates
- graph-neighbor clues
- LLM disambiguation
- confidence thresholds

DoD:
- known aliases không bị split thành nhiều nhân vật
- low confidence không auto merge


## Exit Gate

Không bắt đầu phase tiếp theo cho đến khi:
- automated tests liên quan pass
- documentation cập nhật
- migration/config reproducible
- không có known blocker severity cao
