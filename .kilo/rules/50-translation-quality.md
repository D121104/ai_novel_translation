# Translation Quality Rule

These rules apply to implementation of the runtime translation system.

## Translation priorities

1. Preserve meaning.
2. Preserve all information.
3. Use canonical names.
4. Obey locked glossary.
5. Respect current identity/relationship knowledge.
6. Use correct Vietnamese pronouns/addressing.
7. Preserve character voice.
8. Produce natural Vietnamese.
9. Preserve relevant formatting.

## Context priority

When building model context:

P0:
- current source

P1:
- locked glossary
- canonical names
- identity constraints

P2:
- pronouns/addressing
- immediate previous context

P3:
- relevant current graph facts

P4:
- translation memory

P5:
- semantic memories

P6:
- arc/volume summaries

Drop low-priority context before high-priority context.

Do not maximize context size merely because the model supports it.

## Runtime model routing

Default for personal use:
- extraction/summaries: Luna Low/Medium;
- ordinary translation: Luna Medium;
- QA: Luna Low/Medium;
- difficult translation or failed QA: Terra Medium if configured.

Do not default ordinary prose to High/Max reasoning.
Do not route every chunk to an expensive model.

## QA

Run deterministic QA before LLM QA.

Check at minimum:
- empty output;
- missing paragraph;
- numbers changed;
- missing proper names;
- locked glossary violation;
- malformed markup;
- extreme length anomaly.

Model QA should focus on:
- omission;
- hallucination;
- meaning errors;
- pronoun errors;
- terminology drift;
- identity leakage.

A user-confirmed glossary/name/pronoun choice always outranks model preference.
