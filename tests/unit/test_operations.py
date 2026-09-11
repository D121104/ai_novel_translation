from pathlib import Path

import pytest

from src.core.operations import BackupPlan, DeadLetterQueue, Metrics, disk_status


def test_metrics_are_incremented_and_snapshotted() -> None:
    metrics = Metrics()
    metrics.increment("jobs.completed", 2)
    assert metrics.snapshot() == {"jobs.completed": 2}


def test_dead_letter_queue_is_bounded() -> None:
    queue = DeadLetterQueue(max_items=1)
    queue.add("first", "failed")
    queue.add("second", "failed again")
    assert queue.items == [{"job_id": "second", "error": "failed again"}]


def test_backup_commands_are_explicit() -> None:
    plan = BackupPlan(Path("backups"))
    assert plan.postgres_command("postgresql://db")[:3] == ["pg_dump", "--format=custom", "--file"]
    assert plan.restore_command("postgresql://db")[0] == "pg_restore"


def test_disk_status_reports_real_filesystem() -> None:
    status = disk_status(".", minimum_free_bytes=0)
    assert status.total_bytes >= status.free_bytes >= 0


def test_invalid_metric_increment_is_rejected() -> None:
    with pytest.raises(ValueError):
        Metrics().increment("bad", -1)
