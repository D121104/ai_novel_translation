from dataclasses import dataclass

from src.reprocessing.planner import DependencyIndex, DependencyKind, UnitDependencies


@dataclass(frozen=True)
class StalePlan:
    unit_ids: tuple[str, ...]
    reason: str


def mark_stale(index: DependencyIndex, kind: DependencyKind, dependency_id: str) -> StalePlan:
    return StalePlan(
        tuple(index.affected_units(kind, dependency_id)),
        f"{kind.value}:{dependency_id} changed",
    )


__all__ = ["DependencyIndex", "DependencyKind", "StalePlan", "UnitDependencies", "mark_stale"]
