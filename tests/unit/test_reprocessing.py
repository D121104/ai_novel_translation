from src.reprocessing.planner import DependencyIndex, DependencyKind, UnitDependencies
from src.translation.staleness import mark_stale


def test_glossary_change_only_marks_dependent_units() -> None:
    index = DependencyIndex()
    index.add(UnitDependencies("u1", glossary_ids=frozenset({"g1"})))
    index.add(UnitDependencies("u2", glossary_ids=frozenset({"g2"})))
    index.add(UnitDependencies("u3", entity_ids=frozenset({"e1"})))
    plan = mark_stale(index, DependencyKind.GLOSSARY, "g1")
    assert plan.unit_ids == ("u1",)


def test_multiple_changes_are_deduplicated_and_sorted() -> None:
    index = DependencyIndex()
    index.add(UnitDependencies("u2", fact_ids=frozenset({"f1"})))
    index.add(UnitDependencies("u1", fact_ids=frozenset({"f1"})))
    assert index.plan([(DependencyKind.FACT, "f1"), (DependencyKind.FACT, "f1")]) == ["u1", "u2"]
