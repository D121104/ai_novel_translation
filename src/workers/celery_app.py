import sys

from celery import Celery  # type: ignore[import-untyped]

from src.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "novel-translator",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["src.workers.translation_task"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)
if sys.platform == "win32":
    celery_app.conf.update(worker_pool="solo", worker_concurrency=1)
