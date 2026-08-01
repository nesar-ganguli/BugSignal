from celery import Celery
import sys

from app.config import get_settings


settings = get_settings()
celery_app = Celery(
    "bugsignal",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.workflow_tasks"],
)
celery_app.conf.update(
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# PyTorch's MPS runtime is not fork-safe. Keep local macOS ML tasks in one process;
# Linux production workers retain Celery's prefork pool and can scale horizontally.
if sys.platform == "darwin":
    celery_app.conf.update(worker_pool="solo", worker_concurrency=1)
