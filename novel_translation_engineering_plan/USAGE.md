# Suggested Workflow

## Một phase bình thường

Chọn `novel-engineer` rồi:

```text
Implement Phase 6 from phases/PHASE_06_NEO4J_TEMPORAL_GRAPH.md.
Follow PLAN.md and all project rules.
Delegate only if useful.
Run the relevant tests and ask reviewer to inspect the final diff.
Do not start Phase 7.
```

## Khi muốn sửa GraphRAG

```text
@knowledge-engineer
Review the current GraphRAG retrieval implementation.
Focus on temporal filtering, one-hop graph expansion, Qdrant filtering and reranking.
Do not modify translation prompts.
```

## Khi muốn sửa chất lượng dịch

```text
@translation-engineer
Improve the context builder and deterministic QA.
Keep the existing knowledge schema unchanged.
Prioritize glossary, identities, pronouns, and token-cost control.
```

## Review riêng

```text
@reviewer
Review the current working tree.
Do not edit files.
Run relevant tests/lint/type-check and report only concrete issues.
```

## Không nên

Không bật nhiều subagent cho một task nhỏ.
Không dùng reviewer lặp đi lặp lại đến khi "không còn góp ý".
Không dùng Agent Manager cho project này.
