# Phase 03 — Llm Foundation


Goal: provider abstraction độc lập vendor.

Implement:
- LLMProvider
- OllamaProvider
- OpenAICompatibleProvider
- structured output
- timeout/retry
- token accounting
- response cache

DoD:
- generate
- generate_structured
- cache hit
- provider switch tests


## Exit Gate

Không bắt đầu phase tiếp theo cho đến khi:
- automated tests liên quan pass
- documentation cập nhật
- migration/config reproducible
- không có known blocker severity cao
