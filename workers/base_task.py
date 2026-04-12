"""Base task class with job persistence, error-classified retry logic, structured logging, audit trail, and system event emission."""
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

# ---------------------------------------------------------------------------
# Error classification helpers
# ---------------------------------------------------------------------------

def _extract_http_status(exc: BaseException) -> Optional[int]:
    """Extract an HTTP status code from common exception types."""
    # Direct attribute (httpx, requests, aiohttp, etc.)
    for attr in ("status_code", "status", "code"):
        val = getattr(exc, attr, None)
        if isinstance(val, int) and 100 <= val < 600:
            return val
    # Nested response object
    resp = getattr(exc, "response", None)
    if resp is not None:
        for attr in ("status_code", "status"):
            val = getattr(resp, attr, None)
            if isinstance(val, int) and 100 <= val < 600:
                return val
    return None


def _classify_error(exc: BaseException) -> str:
    """Classify an exception into a retry category.

    Returns one of: 'transient', 'auth', 'permanent', 'unknown'.
    """
    status = _extract_http_status(exc)

    # --- Transient (retry with backoff, no ceiling) ---
    if status in (429, 502, 503, 504):
        return "transient"
    exc_name = type(exc).__name__.lower()
    exc_str = str(exc).lower()
    transient_signals = ("timeout", "connectionerror", "connectionreset",
                         "brokenpipe", "temporaryerror", "unavailable",
                         "econnrefused", "econnreset", "rate limit",
                         "too many requests", "service unavailable",
                         "bad gateway", "gateway timeout")
    if any(s in exc_name or s in exc_str for s in transient_signals):
        return "transient"

    # --- Auth (do NOT retry) ---
    if status in (401, 403):
        return "auth"
    auth_signals = ("unauthorized", "forbidden", "invalid api key",
                    "authentication", "auth_error", "invalid_token",
                    "token expired", "access denied")
    if any(s in exc_name or s in exc_str for s in auth_signals):
        return "auth"

    # --- Permanent (do NOT retry) ---
    if status in (400, 404, 405, 409, 410, 422):
        return "permanent"
    permanent_signals = ("validationerror", "valueerror", "typeerror",
                         "keyerror", "not found", "bad request",
                         "unprocessable", "invalid input")
    if any(s in exc_name or s in exc_str for s in permanent_signals):
        return "permanent"

    # --- Unknown (retry with backoff, emit alert after consecutive failures) ---
    return "unknown"


@lru_cache(maxsize=1)
def _cached_sync_engine():
    return get_sync_engine()


class TrackedTask(Task):
    """Base task that persists status to system_jobs, writes audit entries, and emits system events.

    Error handling uses classification to decide retry strategy:
    - Transient (429, 502, 503, timeouts): retry with exponential backoff, no ceiling
    - Auth (401, 403): no retry, emit alert, mark provider unhealthy
    - Permanent (400, 404, validation): no retry, emit failure event
    - Unknown: retry with exponential backoff, emit alert after consecutive failures

    Guardrails:
    - Failure circuit breaker: trips after 10 failures/hour per provider
    - Records failures for circuit breaker tracking on every on_failure

    System events are the horizontal integration layer — they allow the control layer,
    intelligence layer, and recovery layer to react to job state changes in real time.
    """

    abstract = True
    retry_backoff = True
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
        # Clear circuit breaker failures on success
        self._guardrail_clear_failures()

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        category = _classify_error(exc)
        status_code = _extract_http_status(exc)
        logger.error(
            "worker.task.failed",
            task_name=self.name, task_id=task_id,
            error=str(exc), error_category=category, http_status=status_code,
        )
        now = datetime.now(timezone.utc)

        # Record failure for circuit breaker
        self._guardrail_record_failure()

        if category == "transient":
            # Retry with exponential backoff — no cap on retry count or interval
            retry_count = self.request.retries or 0
            backoff = min(2 ** retry_count * 5, 86400)  # grow unbounded up to 24h per step
            self._persist_status(
                task_id, JobStatus.RETRYING,
                error_message=f"Transient error (retry #{retry_count + 1}): {exc}",
            )
            self._emit_system_event(
                task_id, "orchestration", "job.retrying",
                summary=f"Transient error, retrying: {self.name} — {str(exc)[:200]}",
                severity="warning",
                new_state="retrying",
                previous_state="running",
                details={"error": str(exc)[:500], "category": category,
                         "http_status": status_code, "retry_count": retry_count + 1},
            )
            raise self.retry(exc=exc, countdown=backoff, max_retries=None)

        elif category == "auth":
            # Do NOT retry — emit alert, mark provider unhealthy
            self._persist_status(
                task_id, JobStatus.FAILED,
                error_message=f"Auth error (no retry): {exc}",
                error_traceback=traceback.format_exc(),
                completed_at=now,
            )
            self._write_audit(task_id, "worker.task.failed.auth", {"error": str(exc)})
            self._emit_system_event(
                task_id, "orchestration", "job.failed.auth",
                summary=f"Auth failure (provider unhealthy): {self.name} — {str(exc)[:200]}",
                severity="critical",
                new_state="failed",
                previous_state="running",
                requires_action=True,
                details={"error": str(exc)[:500], "category": category,
                         "http_status": status_code, "task_name": self.name,
                         "action": "mark_provider_unhealthy"},
            )

        elif category == "permanent":
            # Do NOT retry — emit failure event
            self._persist_status(
                task_id, JobStatus.FAILED,
                error_message=f"Permanent error (no retry): {exc}",
                error_traceback=traceback.format_exc(),
                completed_at=now,
            )
            self._write_audit(task_id, "worker.task.failed.permanent", {"error": str(exc)})
            self._emit_system_event(
                task_id, "orchestration", "job.failed.permanent",
                summary=f"Permanent failure: {self.name} — {str(exc)[:200]}",
                severity="error",
                new_state="failed",
                previous_state="running",
                requires_action=False,
                details={"error": str(exc)[:500], "category": category,
                         "http_status": status_code, "task_name": self.name},
            )

        else:
            # Unknown — retry with backoff, emit alert after consecutive failures
            retry_count = self.request.retries or 0
            backoff = min(2 ** retry_count * 10, 86400)
            alert_threshold = 3  # emit alert after this many consecutive retries
            if retry_count >= alert_threshold:
                self._emit_system_event(
                    task_id, "orchestration", "job.consecutive_failures",
                    summary=f"Unknown error, {retry_count + 1} consecutive failures: {self.name}",
                    severity="critical",
                    new_state="retrying",
                    previous_state="running",
                    requires_action=True,
                    details={"error": str(exc)[:500], "category": category,
                             "http_status": status_code, "retry_count": retry_count + 1,
                             "task_name": self.name},
                )
            self._persist_status(
                task_id, JobStatus.RETRYING,
                error_message=f"Unknown error (retry #{retry_count + 1}): {exc}",
            )
            raise self.retry(exc=exc, countdown=backoff, max_retries=None)

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


    # ── Guardrail integration ──────────────────────────────────────────

    def _get_guardrail_engine(self):
        try:
            from packages.guardrails.execution_guardrails import GuardrailEngine
            return GuardrailEngine()
        except Exception:
            return None

    def _guardrail_lane(self) -> str:
        """Derive the lane name from the queue or task name."""
        queue = getattr(self, "queue", None) or "default"
        return queue

    def _guardrail_provider(self) -> str:
        """Derive the provider from the task name (e.g. 'generation_worker' -> 'generation')."""
        name = self.name or ""
        # Extract worker type: workers.generation_worker.tasks.foo -> generation
        parts = name.split(".")
        if len(parts) >= 2:
            worker_part = parts[1]  # e.g. 'generation_worker'
            return worker_part.replace("_worker", "")
        return "unknown"

    def _guardrail_record_failure(self):
        """Record a failure for circuit breaker tracking."""
        try:
            engine = self._get_guardrail_engine()
            if engine:
                engine.record_failure(self._guardrail_lane(), self._guardrail_provider())
        except Exception:
            pass

    def _guardrail_clear_failures(self):
        """Clear failure counter on success."""
        try:
            engine = self._get_guardrail_engine()
            if engine:
                engine.clear_failures(self._guardrail_lane(), self._guardrail_provider())
        except Exception:
            pass


BaseTask = TrackedTask
