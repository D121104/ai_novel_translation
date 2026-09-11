import hashlib
from dataclasses import dataclass
from typing import Protocol

from src.ingestion.parser import ParsedNovel, parse_bytes
from src.ingestion.storage import ObjectStorage


class NovelRepository(Protocol):
    async def find_by_source_hash(self, source_hash: str) -> str | None: ...

    async def save(self, novel: ParsedNovel, source_hash: str, source_path: str) -> str: ...


@dataclass(frozen=True)
class ImportReport:
    novel_id: str
    title: str
    chapter_count: int
    source_path: str
    idempotent: bool


class ImportService:
    def __init__(self, repository: NovelRepository, storage: ObjectStorage) -> None:
        self._repository = repository
        self._storage = storage

    async def import_file(self, filename: str, data: bytes) -> ImportReport:
        source_hash = hashlib.sha256(data).hexdigest()
        existing_id = await self._repository.find_by_source_hash(source_hash)
        if existing_id is not None:
            parsed = parse_bytes(filename, data)
            source_path = f"s3://novels/originals/{source_hash}/{filename}"
            return ImportReport(existing_id, parsed.title, len(parsed.chapters), source_path, True)
        parsed = parse_bytes(filename, data)
        key = f"originals/{source_hash}/{filename}"
        source_path = await self._storage.put(key, data, "application/octet-stream")
        novel_id = await self._repository.save(parsed, source_hash, source_path)
        return ImportReport(novel_id, parsed.title, len(parsed.chapters), source_path, False)
