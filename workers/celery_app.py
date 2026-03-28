"""Celery application configuration with all queues and beat schedule."""
import os

from celery import Celery
from celery.schedules import crontab

broker_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/1")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2")

app = Celery(
    "avatar_revenue_os",
    broker=broker_url,
    backend=result_backend,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_queues={
        "default": {},
        "generation": {},
        "publishing": {},
        "analytics": {},
        "qa": {},
        "learning": {},
        "portfolio": {},
    },
    task_routes={
        "workers.generation_worker.*": {"queue": "generation"},
        "workers.publishing_worker.*": {"queue": "publishing"},
        "workers.analytics_worker.*": {"queue": "analytics"},
        "workers.qa_worker.*": {"queue": "qa"},
        "workers.learning_worker.*": {"queue": "learning"},
        "workers.portfolio_worker.*": {"queue": "portfolio"},
    },
    beat_schedule={
        "trend-scan-every-hour": {
            "task": "workers.analytics_worker.tasks.scan_trends",
            "schedule": crontab(minute=0),
            "options": {"queue": "analytics"},
        },
        "performance-ingest-every-30-min": {
            "task": "workers.analytics_worker.tasks.ingest_performance",
            "schedule": crontab(minute="*/30"),
            "options": {"queue": "analytics"},
        },
        "portfolio-rebalance-daily": {
            "task": "workers.portfolio_worker.tasks.rebalance_portfolios",
            "schedule": crontab(hour=6, minute=0),
            "options": {"queue": "portfolio"},
        },
        "learning-consolidate-daily": {
            "task": "workers.learning_worker.tasks.consolidate_memory",
            "schedule": crontab(hour=3, minute=0),
            "options": {"queue": "learning"},
        },
        "saturation-check-every-6h": {
            "task": "workers.analytics_worker.tasks.check_saturation",
            "schedule": crontab(hour="*/6", minute=15),
            "options": {"queue": "analytics"},
        },
    },
)

app.autodiscover_tasks([
    "workers.generation_worker",
    "workers.publishing_worker",
    "workers.analytics_worker",
    "workers.qa_worker",
    "workers.learning_worker",
    "workers.portfolio_worker",
])
