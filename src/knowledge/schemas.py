from pydantic import BaseModel, Field


class Evidence(BaseModel):
    unit_id: str
    quote: str = Field(min_length=1)
    source_order: int = Field(ge=0)


class EntityCandidate(BaseModel):
    name: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    description: str = ""
    evidence: list[Evidence] = Field(min_length=1)


class AliasCandidate(BaseModel):
    alias: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)


class FactCandidate(BaseModel):
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object_value: str = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)


class RelationCandidate(BaseModel):
    subject: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    object: str = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)


class EventCandidate(BaseModel):
    description: str = Field(min_length=1)
    participants: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(min_length=1)


class TerminologyCandidate(BaseModel):
    source_term: str = Field(min_length=1)
    context: str = ""
    evidence: list[Evidence] = Field(min_length=1)


class ExtractionProposal(BaseModel):
    entities: list[EntityCandidate] = Field(default_factory=list)
    aliases: list[AliasCandidate] = Field(default_factory=list)
    facts: list[FactCandidate] = Field(default_factory=list)
    relations: list[RelationCandidate] = Field(default_factory=list)
    events: list[EventCandidate] = Field(default_factory=list)
    terminology: list[TerminologyCandidate] = Field(default_factory=list)
