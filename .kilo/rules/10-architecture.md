# Architecture Rule

## Database ownership

### PostgreSQL
Canonical source of truth for structured state:
- novel/chapter/unit;
- entity/alias;
- glossary;
- fact metadata/evidence;
- translation versions;
- jobs/checkpoints;
- QA metadata.

### Neo4j
Relationship and graph traversal:
- character relations;
- identity/persona relations;
- organization membership;
- location hierarchy;
- temporal graph queries.

### Qdrant
Retrieval memory:
- source chunks;
- translation memory;
- hierarchical summaries;
- dense/sparse semantic search.

### Redis
Ephemeral queue/coordination only.

### MinIO
Original/imported/exported files.

## Temporal safety

Every plot-sensitive retrieval must support an `as_of_order` / `current_order`
constraint or an equivalent monotonic story position.

For knowledge used at story position N:

```text
observed_at_order <= N
```

For an active temporal relationship:

```text
valid_from_order <= N
AND (valid_to_order IS NULL OR valid_to_order >= N)
```

Do not leak:
- future deaths;
- future betrayals;
- unrevealed identities;
- future relationships;
- future explanations.

Canonical spelling, user-approved Vietnamese names, gender and locked glossary values
may be treated as global consistency metadata when they do not expose plot.

## LLM boundary

LLM output must be parsed/validated before persistence.

Do not let an LLM:
- write arbitrary Cypher directly to canonical state;
- write arbitrary SQL directly to canonical state;
- auto-merge uncertain entities;
- overwrite user-confirmed glossary/facts.

Keep evidence/provenance for extracted facts whenever practical.
