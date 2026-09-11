import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from src.knowledge.schemas import EntityCandidate


def normalize_name(value: str) -> str:
    """Normalize names for matching while preserving the original spelling."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9\u00c0-\u024f\u4e00-\u9fff]+", "", without_marks)


@dataclass(frozen=True)
class CanonicalEntity:
    entity_id: str
    name: str
    entity_type: str
    aliases: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Resolution:
    mention: str
    entity_id: str | None
    confidence: float
    method: str
    auto_merged: bool


class EntityResolver:
    def __init__(
        self, entities: list[CanonicalEntity], *, auto_merge_threshold: float = 0.9
    ) -> None:
        self._entities = entities
        self._threshold = auto_merge_threshold

    def resolve(self, candidate: EntityCandidate) -> Resolution:
        mention = normalize_name(candidate.name)
        scored: list[tuple[float, str, CanonicalEntity]] = []
        for entity in self._entities:
            names = {
                normalize_name(entity.name),
                *(normalize_name(alias) for alias in entity.aliases),
            }
            if mention in names:
                scored.append((1.0, "exact_alias", entity))
                continue
            score = max(
                (SequenceMatcher(None, mention, name).ratio() for name in names), default=0.0
            )
            if normalize_name(candidate.entity_type) == normalize_name(entity.entity_type):
                score = min(1.0, score + 0.05)
            scored.append((score, "fuzzy_lexical", entity))
        if not scored:
            return Resolution(candidate.name, None, 0.0, "no_candidate", False)
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, method, entity = scored[0]
        margin = best_score - scored[1][0] if len(scored) > 1 else best_score
        auto_merged = best_score >= self._threshold and (margin >= 0.05 or method == "exact_alias")
        return Resolution(
            candidate.name,
            entity.entity_id if auto_merged else None,
            round(best_score, 4),
            method if auto_merged else "ambiguous",
            auto_merged,
        )
