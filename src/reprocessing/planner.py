from dataclasses import dataclass, field
from enum import StrEnum


class DependencyKind(StrEnum):
    ENTITY = "entity"
    FACT = "fact"
    GLOSSARY = "glossary"
    MEMORY = "memory"


@dataclass(frozen=True)
class UnitDependencies:
    unit_id: str
    entity_ids: frozenset[str] = frozenset()
    fact_ids: frozenset[str] = frozenset()
    glossary_ids: frozenset[str] = frozenset()
    memory_ids: frozenset[str] = frozenset()

    def contains(self, kind: DependencyKind, dependency_id: str) -> bool:
        return dependency_id in getattr(self, f"{kind.value}_ids")


@dataclass
class DependencyIndex:
    units: dict[str, UnitDependencies] = field(default_factory=dict)

    def add(self, dependencies: UnitDependencies) -> None:
        self.units[dependencies.unit_id] = dependencies

    def affected_units(self, kind: DependencyKind, dependency_id: str) -> list[str]:
        return sorted(
            unit_id
            for unit_id, dependencies in self.units.items()
            if dependencies.contains(kind, dependency_id)
        )

    def plan(self, changes: list[tuple[DependencyKind, str]]) -> list[str]:
        affected = {
            unit_id
            for kind, dependency_id in changes
            for unit_id in self.affected_units(kind, dependency_id)
        }
        return sorted(affected)
