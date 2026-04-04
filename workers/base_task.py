"""Base task class with job persistence, retry logic, structured logging, audit trail, and system event emission."""
from __future__ import annotations

import traceback
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional

import structlog
from celery import Task
from sqlalchemy import update
from sqlalchemy.orm import Session

from packages.db.enums import JobStatus
from packages.db.models.system import AuditLog, SystemJob
from packages.db.models.system_events import SystemEvent
from packages.db.session import get_sync_engine

logger = structlog.get_logger()


@lru_cache(maxsize=1)
def _cached_sync_engine():
    return get_sync_engine()


class TrackedTask(Task):
    """Base task that persists status to system_jobs, writes audit entries, and emits system events.

    System events are the horizontal integration layer — they allow the control layer,
    intelligence layer, and recovery layer to react to job state changes in real time.
    """

    abstract = True
    autoretry_for = (Exception,)
    max_retries = 3
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True

    def before_start(self, task_id, args, kwargs):
        logger.info("worker.task.start", task_name=self.name, task_id=task_id)
        self._persist_status(task_id, JobStatus.RUNNING, started_at=datetime.now(timezone.utc))
        self._emit_system_event(
            task_id, "orchestration", "job.started",
            summary=f"Job started: {self.name}",
            severity="info",
        )

    def on_success(self, retval, task_id, args, kwargs):
        logger.info("worker.task.success", task_name=self.name, task_id=task_id, result_keys=list(retval.keys()) if isinstance(retval, dict) else None)
        now = datetime.now(timezone.utc)
        self._persist_status(
            task_id, JobStatus.COMPLETED,
            completed_at=now,
            output_result=retval if isinstance(retval, dict) else {"result": str(retval)},
        )
        self._write_audit(task_id, "worker.task.completed", retval)
        self._emit_system_event(
            task_id, "orchestration", "job.completed",
            summary=f"Job completed: {self.name}",
            severity="info",
            new_state="completed",
            previous_state="running",
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error("worker.task.failed", task_name=self.name, task_id=task_id, error=str(exc))
        now = datetime.now(timezone.utc)
        self._persist_status(
            task_id, JobStatus.FAILED,
            error_message=str(exc),
            error_traceback=traceback.format_exc(),
            completed_at=now,
        )
        self._write_audit(task_id, "worker.task.failed", {"error": str(exc)})
        self._emit_system_event(
            task_id, "orchestration", "job.failed",
            summary=f"Job failed: {self.name} — {str(exc)[:200]}",
            severity="error",
            new_state="failed",
            previous_state="running",
            requires_action=True,
            details={"error": str(exc)[:500], "task_name": self.name},
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning("worker.task.retry", task_name=self.name, task_id=task_id, error=str(exc))
        self._persist_status(
            task_id, JobStatus.RETRYING,
            error_message=f"Retrying: {exc}",
        )
        self._emit_system_event(
            task_id, "orchestration", "job.retrying",
            summary=f"Job retrying: {self.name} — {str(exc)[:200]}",
            severity="warning",
            new_state="retrying",
            previous_state="running",
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

    def _emit_system_event(
        self,
        task_id: str,
        domain: str,
        event_type: str,
        summary: str,
        severity: str = "info",
        new_state: Optional[str] = None,
        previous_state: Optional[str] = None,
        requires_action: bool = False,
        details: Optional[dict] = None,
    ):
        """Emit a system event from a worker — the horizontal integration glue.

        This allows the control layer, recovery engine, and intelligence layer
        to react to job state changes without polling.
        """
        try:
            engine = _cached_sync_engine()
            with Session(engine) as session:
                event = SystemEvent(
                    event_domain=domain,
                    event_type=event_type,
                    event_severity=severity,
                    entity_type="system_job",
                    previous_state=previous_state,
                    new_state=new_state,
                    actor_type="worker",
                    actor_id=self.name,
                    summary=summary,
                    details={
                        "task_name": self.name,
                        "task_id": task_id,
                        "queue": getattr(self, "queue", None) or "default",
                        **(details or {}),
                    },
                    requires_action=requires_action,
                )
                session.add(event)
                session.commit()
        except Exception:
            logger.exception("worker.emit_event.failed", task_id=task_id, event_type=event_type)


BaseTask = TrackedTask
