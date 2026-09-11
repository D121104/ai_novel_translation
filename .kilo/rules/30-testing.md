# Testing Rule

Every change that can corrupt translation, knowledge or checkpoints requires a test.

## Test priority

### Unit
Test:
- normalization;
- chapter/unit ordering;
- temporal predicates;
- entity resolution scoring;
- glossary rules;
- context budgeting;
- deterministic QA;
- retry/idempotency helpers.

### Integration
Test boundaries with:
- PostgreSQL;
- Neo4j;
- Qdrant;
- Redis;
- MinIO.

Integration tests may be opt-in when infrastructure is unavailable, but must be clearly marked.

### Regression
When fixing a real bug, add a regression test when feasible.

## Quality gates

Use project commands, normally:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy apps src
```

Do not:
- delete failing tests just to get green;
- weaken assertions without a reason;
- mark tests skipped/xfailed to hide a regression.

If a quality gate cannot run, report why.
