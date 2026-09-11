# ADR-002 — Do Not Use LangChain in Core Pipeline Initially

Status: Accepted

Decision:
Core abstractions tự viết:
- LLMProvider
- EmbeddingProvider
- GraphStore
- VectorStore
- Retriever
- Translator

Reason:
Cần kiểm soát token, cache, retry, structured output, temporal filters và debugging.
