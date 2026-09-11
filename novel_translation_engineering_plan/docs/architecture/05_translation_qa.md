# Translation & QA Specification

## Context priority

P0:
- Current source

P1:
- Locked glossary
- Canonical names
- Identity constraints

P2:
- Pronoun/addressing rules
- Immediate previous translation

P3:
- Graph facts

P4:
- Translation memory

P5:
- Semantic memory

P6:
- Arc/volume summary

Khi thiếu token, drop từ P6 lên.

## Translation instructions

Translator phải:
- Preserve meaning
- Không thêm thông tin
- Không bỏ nội dung
- Follow locked glossary
- Preserve character voice
- Preserve paragraph structure
- Respect addressing rules
- Do not reveal hidden identities
- Return translation only

## Deterministic QA

Kiểm tra:
- missing paragraph
- changed numbers
- missing proper names
- locked glossary violation
- malformed markup
- empty output
- extreme length anomaly

## Semantic QA

Kiểm tra:
- meaning preservation
- omission
- hallucination
- pronoun consistency
- terminology
- character voice
- identity leakage
- fluency

## QA decision

Ví dụ configurable:
- >= 0.90 → PASS
- 0.75–0.90 → REPAIR
- < 0.75 → HUMAN_REVIEW
