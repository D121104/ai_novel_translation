from dataclasses import dataclass


@dataclass(frozen=True)
class TemporalRelation:
    relation_id: str
    subject_id: str
    relation_type: str
    object_id: str
    valid_from_order: int
    valid_to_order: int | None = None
    evidence_unit_id: str | None = None


def is_active(relation: TemporalRelation, as_of_order: int) -> bool:
    return relation.valid_from_order <= as_of_order and (
        relation.valid_to_order is None or relation.valid_to_order >= as_of_order
    )
