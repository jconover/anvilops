"""Celery application configuration for AnvilOps."""

from celery import Celery

from app.core.config import settings

celery_app = Celery("anvilops")

celery_app.conf.update(
    broker_url=settings.REDIS_URL,
    result_backend=settings.REDIS_URL,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_max_memory_per_child=400_000,  # 400 MB — recycle workers to prevent leaks
    worker_max_tasks_per_child=50,
    task_soft_time_limit=2400,  # 40 min soft limit
    task_time_limit=3000,  # 50 min hard kill
    result_expires=86400,  # 24 hours
    task_reject_on_worker_lost=True,
)

celery_app.autodiscover_tasks(["app.tasks"])
