"""Batch 9 — fulfillment worker tasks.

Four scheduled tasks that close the autonomous tail of the revenue
circle. All run via Celery beat; all are idempotent and tolerate
missed ticks.

Tasks:
  - drain_pending_production_jobs  (every 60s)
  - dispatch_due_followups         (every 15 min)
  - chase_unpaid_proposals_task    (every 6h)
  - reconcile_stripe_webhooks_task (every 10 min)

Each task runs inside a fresh DB session using the same
``run_async`` / async-session-factory pattern as the existing workers.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import os
import socket
from datetime import datetime, timedelta, timezone

import structlog
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from workers.base_task import TrackedTask


def _fresh_session_factory():
    """Build a fresh async_sessionmaker with a fresh engine inside the
    current thread's event loop.

    We do NOT reuse ``packages.db.session.get_async_session_factory``
    because it caches the engine globally; that engine's connection
    pool binds to the first event loop that opened a connection, and
    subsequent Celery task invocations (each in a fresh thread+loop)
    then crash with ``Future attached to a different loop``.
    """
    db_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(db_url, pool_pre_ping=True, pool_size=2, max_overflow=2)
    return async_sessionmaker(engine, expire_on_commit=False), engine

logger = structlog.get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine from sync Celery task context.

    Always runs inside a fresh ThreadPoolExecutor thread that owns its
    own event loop. This prevents "Future attached to a different loop"
    errors when the persistent Celery worker process invokes us
    repeatedly: each call gets a private loop, and the async session
    factory's engine binds fresh inside that thread instead of leaking
    across invocations.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro)).result()


_WORKER_ID = f"fulfillment_worker@{socket.gethostname()}/{os.getpid()}"
STUCK_IN_PROGRESS_HOURS = 4


# ═══════════════════════════════════════════════════════════════════════════
#  1. drain_pending_production_jobs
# ═══════════════════════════════════════════════════════════════════════════


async def _drain_pending_production_jobs() -> dict:
    """Pick up queued production jobs, transition to in_progress, emit events.

    Also detects stuck in_progress jobs older than 4h and escalates to GM.
    """
    from apps.api.services.event_bus import emit_event
    from apps.api.services.stage_controller import mark_stage
    from packages.db.models.fulfillment import ProductionJob
    from packages.db.models.gm_control import GMEscalation

    Session, engine = _fresh_session_factory()
    async with Session() as db:
        now = datetime.now(timezone.utc)

        # 1a. Pick up pending jobs.
        pending = (
            await db.execute(
                select(ProductionJob).where(
                    ProductionJob.status == "queued",
                    ProductionJob.is_active.is_(True),
                    ProductionJob.picked_up_at.is_(None),
                ).limit(25)
            )
        ).scalars().all()

        picked = 0
        for job in pending:
            job.status = "in_progress"
            job.picked_up_at = now
            job.worker_id = _WORKER_ID
            job.attempt_count = (job.attempt_count or 0) + 1
            job.started_at = job.started_at or now
            picked += 1

            await emit_event(
                db,
                domain="fulfillment",
                event_type="production.job.picked_up",
                summary=f"Production job picked up by fulfillment worker: {job.title[:80]}",
                org_id=job.org_id,
                entity_type="production_job",
                entity_id=job.id,
                previous_state="queued",
                new_state="in_progress",
                actor_type="system",
                actor_id=_WORKER_ID,
                details={
                    "production_job_id": str(job.id),
                    "worker_id": _WORKER_ID,
                    "attempt": job.attempt_count,
                    "avenue_slug": job.avenue_slug,
                },
            )
            try:
                await mark_stage(
                    db, org_id=job.org_id,
                    entity_type="production_job",
                    entity_id=job.id,
                    stage="in_progress",
                )
            except Exception as stage_exc:
                logger.warning(
                    "production.mark_stage_failed",
                    job_id=str(job.id),
                    error=str(stage_exc)[:150],
                )
        await db.flush()

        # 1b. Detect stuck jobs.
        stuck_cutoff = now - timedelta(hours=STUCK_IN_PROGRESS_HOURS)
        stuck_jobs = (
            await db.execute(
                select(ProductionJob).where(
                    ProductionJob.status == "in_progress",
                    ProductionJob.is_active.is_(True),
                    ProductionJob.picked_up_at.isnot(None),
                    ProductionJob.picked_up_at < stuck_cutoff,
                ).limit(25)
            )
        ).scalars().all()

        escalated = 0
        for job in stuck_jobs:
            existing_esc = (
                await db.execute(
                    select(GMEscalation).where(
                        GMEscalation.entity_type == "production_job",
                        GMEscalation.entity_id == job.id,
                        GMEscalation.reason_code == "production_job_stuck",
                        GMEscalation.status == "open",
                    )
                )
            ).scalar_one_or_none()
            if existing_esc is not None:
                continue
            db.add(
                GMEscalation(
                    org_id=job.org_id,
                    reason_code="production_job_stuck",
                    entity_type="production_job",
                    entity_id=job.id,
                    title=f"Production job stuck in_progress: {job.title[:300]}",
                    description=(
                        f"Job {job.id} was picked up at {job.picked_up_at.isoformat()} "
                        f"and has been in_progress for >{STUCK_IN_PROGRESS_HOURS}h "
                        f"without completing. Operator must either call "
                        f"/gm/write/production/{{id}}/submit-output with a real "
                        f"deliverable URL or cancel the job."
                    ),
                    severity="warning",
                    status="open",
                    details_json={
                        "production_job_id": str(job.id),
                        "avenue_slug": job.avenue_slug,
                        "picked_up_at": job.picked_up_at.isoformat(),
                        "worker_id": job.worker_id,
                        "attempt_count": job.attempt_count,
                    },
                )
            )
            escalated += 1

        await db.commit()
        summary = {"picked": picked, "stuck_escalated": escalated}
        logger.info("fulfillment.drain_pending.done", **summary)
    await engine.dispose()
    return summary


@shared_task(
    base=TrackedTask,
    name="workers.fulfillment_worker.tasks.drain_pending_production_jobs",
    queue="default",
)
def drain_pending_production_jobs():
    return _run_async(_drain_pending_production_jobs())


# ═══════════════════════════════════════════════════════════════════════════
#  2. dispatch_due_followups
# ═══════════════════════════════════════════════════════════════════════════


async def _dispatch_due_followups() -> dict:
    """Scan for deliveries with followup_scheduled_at <= now() and
    followup_sent_at IS NULL, send the follow-up email, mark sent.
    """
    from apps.api.services.event_bus import emit_event
    from packages.clients.email_templates import build_delivery_followup
    from packages.clients.external_clients import SmtpEmailClient
    from packages.db.models.clients import Client
    from packages.db.models.delivery import Delivery
    from packages.db.models.fulfillment import ClientProject

    Session, engine = _fresh_session_factory()
    async with Session() as db:
        now = datetime.now(timezone.utc)
        rows = (
            await db.execute(
                select(Delivery).where(
                    Delivery.followup_sent_at.is_(None),
                    Delivery.followup_scheduled_at.isnot(None),
                    Delivery.followup_scheduled_at <= now,
                    Delivery.status == "sent",
                    Delivery.is_active.is_(True),
                ).limit(50)
            )
        ).scalars().all()

        sent = 0
        failed = 0
        skipped_no_smtp = 0

        for delivery in rows:
            client = (
                await db.execute(select(Client).where(Client.id == delivery.client_id))
            ).scalar_one_or_none()
            project = (
                await db.execute(
                    select(ClientProject).where(ClientProject.id == delivery.project_id)
                )
            ).scalar_one_or_none()
            if client is None or project is None:
                delivery.followup_sent_at = now  # prevent retry loop
                failed += 1
                continue

            smtp = await SmtpEmailClient.from_db(db, delivery.org_id)
            if smtp is None:
                skipped_no_smtp += 1
                continue

            built = build_delivery_followup(
                display_name=client.display_name or client.primary_email,
                project_title=project.title,
                deliverable_url=delivery.deliverable_url,
            )
            result = await smtp.send_email(
                to_email=delivery.recipient_email or client.primary_email,
                subject=built["subject"],
                body_html=built["html"],
                body_text=built["text"],
            )
            if result.get("success"):
                delivery.followup_sent_at = now
                sent += 1
                await emit_event(
                    db,
                    domain="fulfillment",
                    event_type="followup.sent",
                    summary=f"Follow-up sent to {delivery.recipient_email} for {project.title[:80]}",
                    org_id=delivery.org_id,
                    entity_type="delivery",
                    entity_id=delivery.id,
                    actor_type="system",
                    actor_id=_WORKER_ID,
                    details={
                        "delivery_id": str(delivery.id),
                        "project_id": str(project.id),
                        "avenue_slug": delivery.avenue_slug,
                        "client_id": str(client.id),
                        "provider": result.get("provider", "smtp"),
                    },
                )
            else:
                failed += 1
                logger.warning(
                    "followup.send_failed",
                    delivery_id=str(delivery.id),
                    error=result.get("error"),
                )

        await db.commit()
        summary = {
            "candidates": len(rows),
            "sent": sent,
            "failed": failed,
            "skipped_no_smtp": skipped_no_smtp,
        }
        logger.info("fulfillment.dispatch_followups.done", **summary)
    await engine.dispose()
    return summary


@shared_task(
    base=TrackedTask,
    name="workers.fulfillment_worker.tasks.dispatch_due_followups",
    queue="default",
)
def dispatch_due_followups():
    return _run_async(_dispatch_due_followups())


# ═══════════════════════════════════════════════════════════════════════════
#  3. chase_unpaid_proposals_task
# ═══════════════════════════════════════════════════════════════════════════


async def _chase_unpaid_proposals_task() -> dict:
    from apps.api.services.proposal_dunning_service import chase_unpaid_proposals
    Session, engine = _fresh_session_factory()
    async with Session() as db:
        result = await chase_unpaid_proposals(db)
    await engine.dispose()
    return result


@shared_task(
    base=TrackedTask,
    name="workers.fulfillment_worker.tasks.chase_unpaid_proposals",
    queue="default",
)
def chase_unpaid_proposals_task():
    return _run_async(_chase_unpaid_proposals_task())


# ═══════════════════════════════════════════════════════════════════════════
#  4. reconcile_stripe_webhooks_task
# ═══════════════════════════════════════════════════════════════════════════


async def _reconcile_stripe_webhooks_task() -> dict:
    from apps.api.services.stripe_reconciliation_service import (
        reconcile_all_stripe_orgs,
    )
    Session, engine = _fresh_session_factory()
    async with Session() as db:
        result = await reconcile_all_stripe_orgs(db)
    await engine.dispose()
    return result


# ═══════════════════════════════════════════════════════════════════════════
#  5. Batch 11 — retention state scanner
# ═══════════════════════════════════════════════════════════════════════════


async def _scan_retention_states_task() -> dict:
    """Every 6h: re-evaluate retention_state for every active client
    across every org. Emits client.retention_state.changed whenever a
    flip occurs so GM surfaces see candidates in real time.
    """
    from apps.api.services.retention_service import scan_all_retention_states
    Session, engine = _fresh_session_factory()
    async with Session() as db:
        result = await scan_all_retention_states(db)
        await db.commit()
    await engine.dispose()
    return result


@shared_task(
    base=TrackedTask,
    name="workers.fulfillment_worker.tasks.scan_retention_states",
    queue="default",
)
def scan_retention_states():
    return _run_async(_scan_retention_states_task())


# ═══════════════════════════════════════════════════════════════════════════
#  6. Batch 13 — overdue invoice scanner
# ═══════════════════════════════════════════════════════════════════════════


async def _scan_overdue_invoices_task() -> dict:
    """Every 6h: flip sent → overdue for invoices whose due_date
    has passed, and open a GMEscalation for each so GM surfaces
    them."""
    from apps.api.services.invoice_service import scan_overdue_invoices
    Session, engine = _fresh_session_factory()
    async with Session() as db:
        result = await scan_overdue_invoices(db)
    await engine.dispose()
    return result


@shared_task(
    base=TrackedTask,
    name="workers.fulfillment_worker.tasks.scan_overdue_invoices",
    queue="default",
)
def scan_overdue_invoices_task():
    return _run_async(_scan_overdue_invoices_task())


@shared_task(
    base=TrackedTask,
    name="workers.fulfillment_worker.tasks.reconcile_stripe_webhooks",
    queue="default",
)
def reconcile_stripe_webhooks_task():
    return _run_async(_reconcile_stripe_webhooks_task())
