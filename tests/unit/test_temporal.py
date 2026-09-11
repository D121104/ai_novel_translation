from src.knowledge.temporal import TemporalRelation, is_active


def test_temporal_relation_visibility() -> None:
    relation = TemporalRelation("r1", "a", "ALLY_OF", "b", valid_from_order=10, valid_to_order=20)
    assert not is_active(relation, 9)
    assert is_active(relation, 10)
    assert is_active(relation, 20)
    assert not is_active(relation, 21)


def test_open_ended_relation_stays_active() -> None:
    relation = TemporalRelation("r1", "a", "KNOWS", "b", valid_from_order=2)
    assert is_active(relation, 100)
