# Data Model

## Core SQL entities

### Novel
- id
- title
- source_language
- target_language
- author
- status
- created_at

### Volume
- id
- novel_id
- index
- title
- summary

### Arc
- id
- volume_id
- index
- title
- summary

### Chapter
- id
- novel_id
- volume_id
- arc_id
- index
- title
- source_text_path
- summary
- status

### TranslationUnit
- id
- chapter_id
- unit_index
- source_order
- source_text
- translated_text
- token_count
- status
- translation_version

### Entity
- id
- novel_id
- entity_type
- canonical_name
- vi_name
- description
- first_seen_order
- last_seen_order
- confidence
- status

### EntityAlias
- id
- entity_id
- alias
- normalized_alias
- alias_type
- valid_from_order
- valid_to_order
- confidence
- source_unit_id

### Fact
- id
- subject_entity_id
- predicate
- object_entity_id
- object_value
- status
- confidence
- valid_from_order
- valid_to_order

### FactEvidence
- id
- fact_id
- chapter_id
- translation_unit_id
- source_order
- extractor_model
- confidence

### GlossaryTerm
- id
- novel_id
- source
- target
- type
- description
- first_seen_order
- locked
- confidence
- created_by

### AddressingRule
- speaker_id
- listener_id
- self_pronoun
- listener_pronoun
- valid_from_order
- valid_to_order
- context
- confidence

## Neo4j node labels

- Character
- Identity
- Location
- Organization
- Item
- Ability
- Race
- Concept
- Event
- Chapter
- Arc
- Volume
- Fact

## Neo4j relationships

- KNOWS
- FRIEND_OF
- ALLY_OF
- ENEMY_OF
- PARENT_OF
- SIBLING_OF
- LOVES
- MARRIED_TO
- MASTER_OF
- DISCIPLE_OF
- MEMBER_OF
- LEADER_OF
- WORKS_FOR
- HAS_IDENTITY
- USES_IDENTITY
- KNOWS_IDENTITY
- OWNS
- USES
- HAS_ABILITY
- LOCATED_AT
- BORN_IN
- PART_OF
- PARTICIPATED_IN
- OCCURRED_AT
- RELATED_TO

## Fact status

- CONFIRMED
- INFERRED
- DISPUTED
- DEPRECATED
- USER_CONFIRMED
