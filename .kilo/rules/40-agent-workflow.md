# Agent Workflow Rule

## Primary workflow

`novel-engineer` is the normal primary agent.

It may delegate only when specialization materially helps.

Recommended routing:

- PostgreSQL / Neo4j / Qdrant / GraphRAG / entity resolution
  → `knowledge-engineer`

- translation / context / prompts / glossary / QA / repair / model routing
  → `translation-engineer`

- final review / diff / tests / regression check
  → `reviewer`

## Delegation limits

- Do not spawn a subagent for a trivial task.
- Do not delegate the same task to multiple agents unless comparing approaches is explicitly useful.
- Subagents must not recursively spawn more agents.
- Do not use Agent Manager for this project.
- Prefer foreground, bounded tasks.
- Keep delegation prompts narrow and include exact files/scope.

## Review

For meaningful code changes:
1. implement;
2. run relevant local checks;
3. ask `reviewer` to inspect the diff when useful;
4. fix concrete issues;
5. stop.

Avoid endless review loops.

## Cost control

- Use the cheapest reasoning level that reliably solves the task.
- Do not use max reasoning for simple file edits/tests.
- Do not repeatedly re-read the entire repository.
- Search/narrow context before opening many files.
- Reuse project skills/rules instead of restating long architecture prompts.
