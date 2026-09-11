import asyncio
import re
from collections.abc import Callable
from typing import Any, TypeVar

from neo4j import Driver, GraphDatabase

from src.core.config import Settings
from src.knowledge.temporal import TemporalRelation

_RELATION_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
ResultT = TypeVar("ResultT")


class TemporalGraph:
    """Neo4j synchronization and story-position-safe relationship queries."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def sync_node(self, entity_id: str, label: str, properties: dict[str, Any]) -> None:
        _validate_label(label)

        def write(driver: Driver) -> None:
            with driver.session() as session:
                session.run(
                    f"MERGE (node:{label} {{entity_id: $entity_id}}) SET node += $properties",
                    entity_id=entity_id,
                    properties=properties,
                ).consume()

        await self._run(write)

    async def sync_relation(self, relation: TemporalRelation) -> None:
        _validate_label(relation.relation_type)

        def write(driver: Driver) -> None:
            with driver.session() as session:
                session.run(
                    f"MATCH (subject {{entity_id: $subject_id}}), "
                    f"(object {{entity_id: $object_id}})\n"
                    f"MERGE (subject)-[edge:{relation.relation_type} "
                    f"{{relation_id: $relation_id}}]->(object)\n"
                    "SET edge.valid_from_order = $valid_from_order,\n"
                    "    edge.valid_to_order = $valid_to_order,\n"
                    "    edge.evidence_unit_id = $evidence_unit_id",
                    **relation.__dict__,
                ).consume()

        await self._run(write)

    async def active_relations(self, entity_id: str, as_of_order: int) -> list[dict[str, Any]]:
        def read(driver: Driver) -> list[dict[str, Any]]:
            with driver.session() as session:
                result = session.run(
                    """MATCH (subject {entity_id: $entity_id})-[edge]->(object)
                    WHERE edge.valid_from_order <= $as_of_order
                      AND (edge.valid_to_order IS NULL OR edge.valid_to_order >= $as_of_order)
                    RETURN subject.entity_id AS subject_id, type(edge) AS relation_type,
                           object.entity_id AS object_id, edge.relation_id AS relation_id""",
                    entity_id=entity_id,
                    as_of_order=as_of_order,
                )
                return [record.data() for record in result]

        return await self._run(read)

    async def _run(self, operation: Callable[[Driver], ResultT]) -> ResultT:
        def execute() -> ResultT:
            driver = GraphDatabase.driver(
                self._settings.neo4j_uri,
                auth=(self._settings.neo4j_user, self._settings.neo4j_password.get_secret_value()),
            )
            try:
                return operation(driver)
            finally:
                driver.close()

        return await asyncio.wait_for(
            asyncio.to_thread(execute), self._settings.health_timeout_seconds
        )


def _validate_label(label: str) -> None:
    if not _RELATION_RE.fullmatch(label):
        raise ValueError("Neo4j labels and relationship types must be uppercase identifiers")
