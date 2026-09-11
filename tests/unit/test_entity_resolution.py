from src.entity_resolution.resolver import CanonicalEntity, EntityResolver, normalize_name
from src.knowledge.schemas import EntityCandidate, Evidence


def candidate(name: str, entity_type: str = "character") -> EntityCandidate:
    return EntityCandidate(
        name=name,
        entity_type=entity_type,
        evidence=[Evidence(unit_id="u1", quote=name, source_order=1)],
    )


def test_exact_and_normalized_alias_resolve_same_entity() -> None:
    resolver = EntityResolver([CanonicalEntity("e1", "Nguyễn An", "character", frozenset({"An"}))])
    assert resolver.resolve(candidate("An")).entity_id == "e1"
    assert normalize_name("Nguyễn An") == normalize_name("nguyen-an")


def test_low_confidence_does_not_auto_merge() -> None:
    resolver = EntityResolver([CanonicalEntity("e1", "Alexander", "character")])
    result = resolver.resolve(candidate("Zelda"))
    assert result.entity_id is None
    assert result.auto_merged is False


def test_ambiguous_candidates_do_not_auto_merge() -> None:
    resolver = EntityResolver(
        [CanonicalEntity("e1", "Mina", "character"), CanonicalEntity("e2", "Miko", "character")]
    )
    result = resolver.resolve(candidate("Mino"))
    assert result.entity_id is None
    assert result.method == "ambiguous"
