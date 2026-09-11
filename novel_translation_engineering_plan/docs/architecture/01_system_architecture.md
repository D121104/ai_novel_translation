# System Architecture

## High-level flow

```text
Source Novel
   ↓
Ingestion
   ↓
Chunking
   ↓
Knowledge Extraction ──→ PostgreSQL
   │                       ↓
   │                     Neo4j
   │
   └────────────────────→ Qdrant
                            ↓
                       GraphRAG
                            ↓
                     Context Builder
                            ↓
                    Translation LLM
                            ↓
                      QA / Repair
                            ↓
                    Translation Store
                            ↓
                          Export
```

## Infrastructure responsibilities

### PostgreSQL
Canonical state và transaction consistency.

### Neo4j
Relationship traversal, temporal graph, identity graph.

### Qdrant
Dense/sparse semantic retrieval và translation memory.

### Redis
Queue broker, short-lived coordination, retry scheduling.

### MinIO
Original EPUB/TXT/JSON, parsed snapshots, exports.

## Service boundaries

- `api`: HTTP API + orchestration entry points
- `worker`: background pipeline
- `domain`: business rules
- `knowledge`: extraction/resolution
- `retrieval`: GraphRAG
- `translation`: context/prompt/QA
- `infrastructure`: DB adapters
