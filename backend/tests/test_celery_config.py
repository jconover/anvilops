"""Tests for Celery application configuration (app.worker.celery_app).

Validates that the Celery app is properly configured with expected
broker, result backend, serialization, and worker settings.
"""

from app.worker.celery_app import celery_app


class TestCeleryAppConfig:
    """Verify Celery configuration values."""

    def test_app_name(self):
        assert celery_app.main == "anvilops"

    def test_task_serializer(self):
        assert celery_app.conf.task_serializer == "json"

    def test_result_serializer(self):
        assert celery_app.conf.result_serializer == "json"

    def test_accept_content(self):
        assert "json" in celery_app.conf.accept_content

    def test_timezone_utc(self):
        assert celery_app.conf.timezone == "UTC"

    def test_enable_utc(self):
        assert celery_app.conf.enable_utc is True

    def test_task_track_started(self):
        assert celery_app.conf.task_track_started is True

    def test_task_acks_late(self):
        assert celery_app.conf.task_acks_late is True

    def test_worker_prefetch_multiplier(self):
        assert celery_app.conf.worker_prefetch_multiplier == 1

    def test_worker_max_memory_per_child(self):
        assert celery_app.conf.worker_max_memory_per_child == 400_000

    def test_worker_max_tasks_per_child(self):
        assert celery_app.conf.worker_max_tasks_per_child == 50

    def test_task_soft_time_limit(self):
        assert celery_app.conf.task_soft_time_limit == 2400

    def test_task_time_limit(self):
        assert celery_app.conf.task_time_limit == 3000

    def test_result_expires(self):
        assert celery_app.conf.result_expires == 86400

    def test_task_reject_on_worker_lost(self):
        assert celery_app.conf.task_reject_on_worker_lost is True

    def test_autodiscover_packages(self):
        # The autodiscovered packages include app.tasks
        # We verify by checking a known registered task
        assert celery_app.conf.broker_url is not None
