"""Base task class with job persistence, retry logic, and error tracking."""
import traceback
import uuid
from datetime import datetime, timezone

from celery import Task
from sqlalchemy import update

from packages.db.enums import JobStatus
from packages.db.models.system import SystemJob
from packages.db.session import get_sync_engine

from sqlalchemy.orm import Session


class TrackedTask(Task):
    """Base task that persists status, retries, and errors to system_jobs."""

    abstract = True
    autoretry_for = (Exception,)
    max_retries = 3
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True

    def before_start(self, task_id, args, kwargs):
        self._persist_status(task_id, JobStatus.RUNNING, started_at=datetime.now(timezone.utc))

    def on_success(self, retval, task_id, args, kwargs):
        self._persist_status(
            task_id, JobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            output_result=retval if isinstance(retval, dict) else {"result": str(retval)},
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        self._persist_status(
            task_id, JobStatus.FAILED,
            error_message=str(exc),
            error_traceback=traceback.format_exc(),
            completed_at=datetime.now(timezone.utc),
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        self._persist_status(
            task_id, JobStatus.RETRYING,
            error_message=f"Retrying: {exc}",
        )

    def _persist_status(self, task_id: str, status: JobStatus, **extra):
        try:
            engine = get_sync_engine()
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
                        queue=self.queue or "default",
                        status=status,
                        **extra,
                    )
                    session.add(job)
                session.commit()
        except Exception:
            pass
