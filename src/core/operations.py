"""Operational safeguards that do not depend on a monitoring platform."""

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock


@dataclass
class Metrics:
    """Small process-local counters suitable for a personal deployment."""

    _counters: dict[str, int] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def increment(self, name: str, amount: int = 1) -> None:
        if amount < 0:
            raise ValueError("metric increments cannot be negative")
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + amount

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)


@dataclass(frozen=True)
class DiskStatus:
    path: str
    free_bytes: int
    total_bytes: int
    below_threshold: bool


def disk_status(path: str | Path, *, minimum_free_bytes: int) -> DiskStatus:
    usage = shutil.disk_usage(path)
    return DiskStatus(str(path), usage.free, usage.total, usage.free < minimum_free_bytes)


@dataclass
class DeadLetterQueue:
    """Bounded in-memory dead-letter queue for failed local jobs."""

    max_items: int = 1000
    items: list[dict[str, str]] = field(default_factory=list)

    def add(self, job_id: str, error: str) -> None:
        if not job_id or not error:
            raise ValueError("job_id and error are required")
        if len(self.items) >= self.max_items:
            self.items.pop(0)
        self.items.append({"job_id": job_id, "error": error})


@dataclass(frozen=True)
class BackupPlan:
    output_dir: Path

    def postgres_command(self, dsn: str, filename: str = "postgres.sql") -> list[str]:
        return ["pg_dump", "--format=custom", "--file", str(self.output_dir / filename), dsn]

    def restore_command(self, dsn: str, filename: str = "postgres.sql") -> list[str]:
        return ["pg_restore", "--exit-on-error", "--dbname", dsn, str(self.output_dir / filename)]
