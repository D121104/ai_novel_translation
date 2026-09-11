# AGENTS.md — AI Novel Translation Studio

This repository is a personal-use AI novel translation application.

Before making changes:
1. Read `PLAN.md` if present.
2. Read the current phase specification under `phases/`.
3. Read relevant files under `.kilo/rules/`.
4. Load the relevant project skill when available.

## Priority

1. Correctness
2. Translation consistency
3. Temporal safety
4. Resumability
5. Simplicity
6. Cost
7. Performance
8. UI polish

## Core architecture

- PostgreSQL = canonical structured truth.
- Neo4j = relationship/identity/temporal graph.
- Qdrant = semantic memory and translation memory.
- Redis = temporary job coordination.
- MinIO = source/import/export object storage.

Do not casually merge these responsibilities.

## Hard constraints

- Never expose future plot knowledge to an earlier translation position.
- LLM output is a proposal, not canonical truth.
- Do not aggressively auto-merge uncertain entities.
- Do not add enterprise infrastructure to a personal app unless requested.
- Do not skip phases or implement large future-phase features opportunistically.
- Do not read or expose secrets unless explicitly necessary and approved.
- Long-running jobs must eventually be resumable/idempotent.

## Development behavior

Prefer small, verifiable changes.

After implementation:
- run relevant tests;
- run lint/type checks when practical;
- summarize changed files;
- report any deviation from the current phase specification.

Do not claim success if tests were not run or failed.
