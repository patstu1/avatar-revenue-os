"""Base task class with job persistence, retry logic, structured logging, and audit trail."""
from __future__ import annotations

import traceback
from datetime import datetime, timezone
from functools import lru_cache

import structlog
from celery import Task
from sqlalchemy import update
from sqlalchemy.orm import Session

from packages.db.enums import JobStatus
from packages.db.models.system import AuditLog, SystemJob
from packages.db.session import get_sync_engine

logger = structlog.get_logger()


@lru_cache(maxsize=1)
def _cached_sync_engine():
    return get_sync_engine()


class TrackedTask(Task):
    """Base task that persists status to system_jobs and writes audit entries for scheduled runs."""

    abstract = True
    autoretry_for = (Exception,)
    max_retries = 3
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True

    def before_start(self, task_id, args, kwargs):
        logger.info("worker.task.start", task_name=self.name, task_id=task_id)
        self._persist_status(task_id, JobStatus.RUNNING, started_at=datetime.now(timezone.utc))

    def on_success(self, retval, task_id, args, kwargs):
        logger.info("worker.task.success", task_name=self.name, task_id=task_id, result_keys=list(retval.keys()) if isinstance(retval, dict) else None)
        self._persist_status(
            task_id, JobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            output_result=retval if isinstance(retval, dict) else {"result": str(retval)},
        )
        self._write_audit(task_id, "worker.task.completed", retval)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error("worker.task.failed", task_name=self.name, task_id=task_id, error=str(exc))
        self._persist_status(
            task_id, JobStatus.FAILED,
            error_message=str(exc),
            error_traceback=traceback.format_exc(),
            completed_at=datetime.now(timezone.utc),
        )
        self._write_audit(task_id, "worker.task.failed", {"error": str(exc)})

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning("worker.task.retry", task_name=self.name, task_id=task_id, error=str(exc))
        self._persist_status(
            task_id, JobStatus.RETRYING,
            error_message=f"Retrying: {exc}",
        )

    def _persist_status(self, task_id: str, status: JobStatus, **extra):
        try:
            engine = _cached_sync_engine()
            with Session(engine) as session:
                stmt = (
                    update(SystemJob)
                    .where(SystemJob.celery_task_id == task_id)
                    .values(status=status, **extra)
                )
                result = session.execute(stmt)
                if result.rowcount == 0:
                    job = SystemJob(
                        celery_task_id=task_id,
                        job_name=self.name,
                        job_type="celery_task",
                        queue=getattr(self, "queue", None) or "default",
                        status=status,
                        **extra,
                    )
                    session.add(job)
                session.commit()
        except Exception:
            logger.exception("worker.persist_status.failed", task_id=task_id, status=status.value)

    def _write_audit(self, task_id: str, action: str, details):
        try:
            engine = _cached_sync_engine()
            with Session(engine) as session:
                entry = AuditLog(
                    actor_type="system",
                    action=action,
                    entity_type="celery_task",
                    details={
                        "task_name": self.name,
                        "task_id": task_id,
                        **(details if isinstance(details, dict) else {"result": str(details)}),
                    },
                )
                session.add(entry)
                session.commit()
        except Exception:
            logger.exception("worker.write_audit.failed", task_id=task_id, action=action)


BaseTask = TrackedTask
