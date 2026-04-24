"""QA + delivery + followup orchestration (Batch 3D).

Wires production_jobs through QA → retry → delivery → followup.

Entry points:
  submit_production_output(db, job, *, output_url, ...)
      → marks job status=qa_pending, runs auto-QA, dispatches on pass

  run_qa_review(db, job, *, ...)
      → writes ProductionQAReview + updates job.status + emits
        qa.passed | qa.failed; on failure, either retries (resets
        status=running + attempt_count += 1) or terminates
        (status=failed) when retry limit is reached

  dispatch_delivery(db, job, *, channel, ...)
      → writes Delivery row, transitions job to completed, emits
        delivery.sent + schedules a followup

  schedule_followup(db, delivery, *, when)
      → sets followup_scheduled_at + emits followup.scheduled
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.db.models.clients import Client
from packages.db.models.delivery import Delivery, ProductionQAReview
from packages.db.models.fulfillment import ClientProject, ProductionJob

logger = structlog.get_logger()

QA_PASS_THRESHOLD = 0.75
DEFAULT_FOLLOWUP_DAYS = 7


# ═══════════════════════════════════════════════════════════════════════════
#  Output submission (production worker hands off to QA here)
# ═══════════════════════════════════════════════════════════════════════════


async def submit_production_output(
    db: AsyncSession,
    *,
    job: ProductionJob,
    output_url: str | None = None,
    output_payload: dict | None = None,
    auto_qa: bool = True,
    auto_dispatch: bool = True,
) -> dict:
    """Record output URL on the job, transition to qa_pending, optionally
    run auto-QA and dispatch delivery on pass.

    Returns a dict summary suitable for API responses.
    """
    datetime.now(timezone.utc)
    job.output_url = output_url
    job.output_payload_json = output_payload
    job.status = "qa_pending"
    await db.flush()
    try:
        from apps.api.services.stage_controller import mark_stage
        await mark_stage(
            db, org_id=job.org_id,
            entity_type="production_job", entity_id=job.id, stage="qa_pending",
        )
    except Exception as stage_exc:
        logger.warning("stage_controller.mark_failed",
                        entity="production_job", error=str(stage_exc)[:150])

    result_summary: dict = {"production_job_id": str(job.id), "output_url": output_url}

    if not auto_qa:
        return {**result_summary, "qa": None, "delivery": None}

    review = await run_qa_review(db, job=job)
    result_summary["qa"] = {
        "review_id": str(review.id),
        "result": review.result,
        "composite_score": review.composite_score,
        "attempt": review.attempt,
    }

    if review.result == "passed" and auto_dispatch:
        delivery = await dispatch_delivery(db, job=job)
        result_summary["delivery"] = {
            "delivery_id": str(delivery.id),
            "status": delivery.status,
            "followup_scheduled_at": delivery.followup_scheduled_at.isoformat()
            if delivery.followup_scheduled_at else None,
        }
    else:
        result_summary["delivery"] = None

    return result_summary


# ═══════════════════════════════════════════════════════════════════════════
#  QA review
# ═══════════════════════════════════════════════════════════════════════════


async def run_qa_review(
    db: AsyncSession,
    *,
    job: ProductionJob,
    scores: dict | None = None,
    issues: list | None = None,
    notes: str | None = None,
    reviewer_type: str = "auto",
    reviewer_id: str | None = None,
    force_fail: bool = False,
) -> ProductionQAReview:
    """Create a ProductionQAReview for the current attempt of ``job`` and
    transition the job.

    Outcomes:
      - composite_score >= QA_PASS_THRESHOLD and not force_fail
          → result=passed, job.status=qa_passed, emit qa.passed
      - otherwise and attempt_count < retry_limit
          → result=failed, job.status=running (retry queued),
            job.attempt_count += 1, emit qa.failed
      - otherwise
          → result=failed, job.status=failed (terminal), emit qa.failed
            with terminal=True flag
    """
    scores = dict(scores or {})
    composite = scores.get("composite")
    if composite is None:
        numeric_scores = [v for v in scores.values() if isinstance(v, (int, float))]
        composite = (
            sum(numeric_scores) / len(numeric_scores)
            if numeric_scores else 0.85  # default-pass if nothing provided
        )
    composite = max(0.0, min(1.0, float(composite)))

    passed = (not force_fail) and composite >= QA_PASS_THRESHOLD

    review = ProductionQAReview(
        org_id=job.org_id,
        production_job_id=job.id,
        project_id=job.project_id,
        attempt=job.attempt_count,
        result="passed" if passed else "failed",
        composite_score=composite,
        scores_json=scores,
        issues_json={"issues": issues} if issues else None,
        notes=notes,
        reviewer_type=reviewer_type,
        reviewer_id=reviewer_id,
    )
    db.add(review)
    await db.flush()

    job.last_qa_report_id = review.id
    now = datetime.now(timezone.utc)

    if passed:
        job.status = "qa_passed"
        await db.flush()
        await emit_event(
            db,
            domain="fulfillment",
            event_type="qa.passed",
            summary=f"QA passed for job {job.title[:80]} (score {composite:.2f})",
            org_id=job.org_id,
            entity_type="production_job",
            entity_id=job.id,
            previous_state="qa_pending",
            new_state="qa_passed",
            actor_type=reviewer_type,
            actor_id=reviewer_id,
            details={
                "production_job_id": str(job.id),
                "review_id": str(review.id),
                "attempt": job.attempt_count,
                "composite_score": composite,
            },
        )
        logger.info("qa.passed", production_job_id=str(job.id), score=composite)
        try:
            from apps.api.services.stage_controller import mark_stage
            await mark_stage(
                db, org_id=job.org_id,
                entity_type="production_job", entity_id=job.id, stage="qa_passed",
            )
        except Exception as stage_exc:
            logger.warning("stage_controller.mark_failed",
                            entity="production_job", error=str(stage_exc)[:150])
        return review

    # Failure path — decide retry vs terminal
    if job.attempt_count < job.retry_limit:
        # Retry: reset to running, bump attempt
        job.status = "running"
        job.attempt_count += 1
        job.started_at = now
        await db.flush()
        terminal = False
    else:
        job.status = "failed"
        job.completed_at = now
        await db.flush()
        terminal = True

    await emit_event(
        db,
        domain="fulfillment",
        event_type="qa.failed",
        summary=f"QA failed for job {job.title[:80]} (attempt {review.attempt}, terminal={terminal})",
        org_id=job.org_id,
        entity_type="production_job",
        entity_id=job.id,
        previous_state="qa_pending",
        new_state=job.status,
        actor_type=reviewer_type,
        actor_id=reviewer_id,
        severity="warning" if not terminal else "error",
        details={
            "production_job_id": str(job.id),
            "review_id": str(review.id),
            "attempt": review.attempt,
            "composite_score": composite,
            "terminal": terminal,
            "next_attempt": job.attempt_count if not terminal else None,
            "issues": issues or [],
        },
    )
    logger.info(
        "qa.failed",
        production_job_id=str(job.id),
        attempt=review.attempt,
        terminal=terminal,
    )
    return review


# ═══════════════════════════════════════════════════════════════════════════
#  Delivery dispatch
# ═══════════════════════════════════════════════════════════════════════════


async def dispatch_delivery(
    db: AsyncSession,
    *,
    job: ProductionJob,
    channel: str = "email",
    subject: str | None = None,
    message: str | None = None,
    deliverable_url: str | None = None,
    followup_days: int = DEFAULT_FOLLOWUP_DAYS,
) -> Delivery:
    """Create a Delivery row, transition job to completed, emit
    delivery.sent, and schedule a follow-up (emits followup.scheduled).

    Idempotent — if an active Delivery already exists for this
    production_job_id, the existing row is returned.
    """
    existing = (
        await db.execute(
            select(Delivery).where(
                Delivery.production_job_id == job.id,
                Delivery.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    project = (
        await db.execute(select(ClientProject).where(ClientProject.id == job.project_id))
    ).scalar_one()
    client = (
        await db.execute(select(Client).where(Client.id == project.client_id))
    ).scalar_one()

    now = datetime.now(timezone.utc)
    default_subject = f"Delivery: {job.title[:400]}"
    default_message = (
        f"Hi {client.display_name or client.primary_email},\n\n"
        f"Your {project.title} is ready.\n\n"
        f"{('View it here: ' + (deliverable_url or job.output_url)) if (deliverable_url or job.output_url) else 'Attached.'}\n\n"
        f"Let me know if anything needs adjustment.\n\n"
        f"— The team"
    )

    followup_at = now + timedelta(days=max(1, followup_days))

    delivery = Delivery(
        org_id=job.org_id,
        client_id=project.client_id,
        project_id=project.id,
        production_job_id=job.id,
        title=job.title[:500],
        channel=channel,
        status="sent",
        deliverable_url=deliverable_url or job.output_url,
        recipient_email=client.primary_email,
        subject=(subject or default_subject)[:1000],
        message=message or default_message,
        sent_at=now,
        followup_scheduled_at=followup_at,
        # Batch 9: carry avenue_slug from the job (back-fill chain).
        avenue_slug=job.avenue_slug or project.avenue_slug or client.avenue_slug,
    )
    db.add(delivery)
    await db.flush()

    job.status = "completed"
    job.completed_at = now
    await db.flush()

    # Also mark the project completed if all its jobs are done
    remaining = (
        await db.execute(
            select(ProductionJob).where(
                ProductionJob.project_id == project.id,
                ProductionJob.is_active.is_(True),
                ProductionJob.status.notin_(("completed", "cancelled", "failed")),
            )
        )
    ).scalars().all()
    if not remaining:
        project.status = "completed"
        project.completed_at = now
        await db.flush()

    await emit_event(
        db,
        domain="fulfillment",
        event_type="delivery.sent",
        summary=f"Delivery sent to {client.primary_email}",
        org_id=job.org_id,
        entity_type="delivery",
        entity_id=delivery.id,
        new_state="sent",
        actor_type="system",
        actor_id="qa_delivery_service",
        details={
            "delivery_id": str(delivery.id),
            "production_job_id": str(job.id),
            "project_id": str(project.id),
            "client_id": str(project.client_id),
            "channel": channel,
            "recipient_email": client.primary_email,
            "deliverable_url": delivery.deliverable_url,
        },
    )
    logger.info(
        "delivery.sent",
        delivery_id=str(delivery.id),
        production_job_id=str(job.id),
    )

    # Schedule follow-up (emits followup.scheduled)
    await emit_event(
        db,
        domain="fulfillment",
        event_type="followup.scheduled",
        summary=f"Follow-up scheduled for {followup_at.date().isoformat()}",
        org_id=job.org_id,
        entity_type="delivery",
        entity_id=delivery.id,
        new_state="followup_scheduled",
        actor_type="system",
        actor_id="qa_delivery_service",
        details={
            "delivery_id": str(delivery.id),
            "client_id": str(project.client_id),
            "followup_scheduled_at": followup_at.isoformat(),
            "followup_days": followup_days,
        },
    )
    logger.info(
        "followup.scheduled",
        delivery_id=str(delivery.id),
        followup_at=followup_at.isoformat(),
    )
    return delivery


async def schedule_followup(
    db: AsyncSession,
    *,
    delivery: Delivery,
    when: datetime,
) -> Delivery:
    """Re-schedule a follow-up on an existing delivery. Emits
    followup.scheduled."""
    delivery.followup_scheduled_at = when
    await db.flush()
    await emit_event(
        db,
        domain="fulfillment",
        event_type="followup.scheduled",
        summary=f"Follow-up re-scheduled for {when.date().isoformat()}",
        org_id=delivery.org_id,
        entity_type="delivery",
        entity_id=delivery.id,
        new_state="followup_scheduled",
        actor_type="system",
        actor_id="qa_delivery_service",
        details={"delivery_id": str(delivery.id), "followup_scheduled_at": when.isoformat()},
    )
    return delivery
