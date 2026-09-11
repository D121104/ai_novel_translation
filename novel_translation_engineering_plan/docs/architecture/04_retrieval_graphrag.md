# Retrieval & GraphRAG Specification

## Retrieval pipeline

```text
Current TranslationUnit
        ↓
Entity mention detection
        ↓
Canonical entity lookup
        ↓
Neo4j 1-hop expansion
        ↓
Qdrant hybrid candidate retrieval
        ↓
Temporal filtering
        ↓
Rerank
        ↓
Token-budget selection
        ↓
RetrievalContext
```

## Graph retrieval defaults

- Default depth: 1 hop
- Allow 2 hops only for explicit need
- Never dump whole graph into prompt

## Qdrant collections

### novel_chunks
Payload:
- novel_id
- volume_id
- arc_id
- chapter_id
- chapter_index
- unit_index
- source_order
- entity_ids
- character_ids
- location_ids
- organization_ids
- text_type

### translation_memory
Payload:
- source_text
- translated_text
- chapter
- source_order
- entity_ids
- term_ids
- translation_version
- qa_score
- human_approved

### story_summaries
Payload:
- novel_id
- level
- entity_ids
- source_order_start
- source_order_end
- summary_type

## Hybrid retrieval

Use:
- dense semantic
- sparse lexical
- metadata filtering
- fusion

Initial candidate count:
- top 30

After rerank:
- top 5–10

## Reranking features

- semantic similarity
- exact name match
- entity overlap
- temporal proximity
- same arc
- relation relevance
- source reliability
