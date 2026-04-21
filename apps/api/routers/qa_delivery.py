"""QA + delivery router (Batch 3D).

Operator-facing hooks into the production → QA → delivery loop. Every
state change is auditable via SystemEvent emissions performed inside
the underlying service; these endpoints are thin wrappers for manual
control.
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select

from apps.api.deps import DBSession, OperatorUser
from apps.api.services.qa_delivery_service import (
    dispatch_delivery as svc_dispatch,
    run_qa_review,
    schedule_followup as svc_schedule_followup,
    submit_production_output,
)
from packages.db.models.delivery import Delivery, ProductionQAReview
from packages.db.models.fulfillment import ProductionJob

logger = structlog.get_logger()

router = APIRouter(tags=["QA & Delivery"])


# ── Production output submission (dev/operator hook) ────────────────────────


class SubmitOutputBody(BaseModel):
    output_url: Optional[str] = None
    output_payload: Optional[dict] = None
    auto_qa: bool = True
    auto_dispatch: bool = True


@router.post("/production-jobs/{job_id}/submit-output")
async def submit_output(
    job_id: str,
    body: SubmitOutputBody,
    current_user: OperatorUser,
    db: DBSession,
):
    job = await _require_owned_job(db, job_id, current_user.organization_id)
    result = await submit_production_output(
        db,
        job=job,
        output_url=body.output_url,
        output_payload=body.output_payload,
        auto_qa=body.auto_qa,
        auto_dispatch=body.auto_dispatch,
    )
    await db.commit()
    return result


# ── Manual QA review ────────────────────────────────────────────────────────


class ReviewBody(BaseModel):
    scores: Optional[dict] = None
    issues: Optional[list] = None
    notes: Optional[str] = None
    force_fail: bool = False


@router.post("/production-jobs/{job_id}/qa-review", status_code=201)
async def submit_qa_review(
    job_id: str,
    body: ReviewBody,
    current_user: OperatorUser,
    db: DBSession,
):
    job = await _require_owned_job(db, job_id, current_user.organization_id)
    if job.status not in ("qa_pending", "running", "qa_failed"):
        raise HTTPException(
            400,
            f"Cannot QA a job in status={job.status}; expected qa_pending/running/qa_failed",
        )
    review = await run_qa_review(
        db,
        job=job,
        scores=body.scores,
        issues=body.issues,
        notes=body.notes,
        reviewer_type="operator",
        reviewer_id=current_user.email,
        force_fail=body.force_fail,
    )
    await db.commit()
    return {
        "id": str(review.id),
        "production_job_id": str(review.production_job_id),
        "result": review.result,
        "attempt": review.attempt,
        "composite_score": review.composite_score,
        "job_status_after": job.status,
        "job_attempt_count_after": job.attempt_count,
    }


# ── Manual delivery dispatch ────────────────────────────────────────────────


class DispatchBody(BaseModel):
    channel: str = "email"
    subject: Optional[str] = None
    message: Optional[str] = None
    deliverable_url: Optional[str] = None
    followup_days: int = 7


@router.post("/production-jobs/{job_id}/dispatch-delivery", status_code=201)
async def dispatch_delivery_route(
    job_id: str,
    body: DispatchBody,
    current_user: OperatorUser,
    db: DBSession,
):
    job = await _require_owned_job(db, job_id, current_user.organization_id)
    if job.status not in ("qa_passed", "completed"):
        raise HTTPException(
            400,
            f"Cannot dispatch from status={job.status}; expected qa_passed/completed",
        )
    delivery = await svc_dispatch(
        db,
        job=job,
        channel=body.channel,
        subject=body.subject,
        message=body.message,
        deliverable_url=body.deliverable_url,
        followup_days=body.followup_days,
    )
    await db.commit()
    return _delivery_summary(delivery)


# ── Deliveries ──────────────────────────────────────────────────────────────


@router.get("/deliveries")
async def list_deliveries(
    current_user: OperatorUser,
    db: DBSession,
    status: Optional[str] = None,
    limit: int = 50,
):
    q = select(Delivery).where(
        Delivery.org_id == current_user.organization_id,
        Delivery.is_active.is_(True),
    )
    if status:
        q = q.where(Delivery.status == status)
    q = q.order_by(desc(Delivery.created_at)).limit(max(1, min(200, limit)))
    rows = (await db.execute(q)).scalars().all()
    return [_delivery_summary(d) for d in rows]


@router.get("/deliveries/{delivery_id}")
async def get_delivery(
    delivery_id: str,
    current_user: OperatorUser,
    db: DBSession,
):
    did = _parse_uuid(delivery_id)
    delivery = (
        await db.execute(select(Delivery).where(Delivery.id == did))
    ).scalar_one_or_none()
    if delivery is None or delivery.org_id != current_user.organization_id:
        raise HTTPException(404, "Delivery not found")
    return {
        **_delivery_summary(delivery),
        "client_id": str(delivery.client_id),
        "project_id": str(delivery.project_id),
        "production_job_id": str(delivery.production_job_id),
        "subject": delivery.subject,
        "message": delivery.message,
        "metadata": delivery.metadata_json,
    }


class RescheduleFollowupBody(BaseModel):
    followup_scheduled_at: datetime


@router.post("/deliveries/{delivery_id}/schedule-followup")
async def reschedule_followup(
    delivery_id: str,
    body: RescheduleFollowupBody,
    current_user: OperatorUser,
    db: DBSession,
):
    did = _parse_uuid(delivery_id)
    delivery = (
        await db.execute(select(Delivery).where(Delivery.id == did))
    ).scalar_one_or_none()
    if delivery is None or delivery.org_id != current_user.organization_id:
        raise HTTPException(404, "Delivery not found")
    await svc_schedule_followup(db, delivery=delivery, when=body.followup_scheduled_at)
    await db.commit()
    return {"id": str(delivery.id), "followup_scheduled_at": body.followup_scheduled_at.isoformat()}


# ── QA reviews list ─────────────────────────────────────────────────────────


@router.get("/qa-reviews")
async def list_qa_reviews(
    current_user: OperatorUser,
    db: DBSession,
    result: Optional[str] = None,
    limit: int = 50,
):
    q = select(ProductionQAReview).where(
        ProductionQAReview.org_id == current_user.organization_id,
        ProductionQAReview.is_active.is_(True),
    )
    if result:
        q = q.where(ProductionQAReview.result == result)
    q = q.order_by(desc(ProductionQAReview.created_at)).limit(max(1, min(200, limit)))
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id": str(r.id),
            "production_job_id": str(r.production_job_id),
            "project_id": str(r.project_id),
            "attempt": r.attempt,
            "result": r.result,
            "composite_score": r.composite_score,
            "reviewer_type": r.reviewer_type,
            "reviewer_id": r.reviewer_id,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _delivery_summary(d: Delivery) -> dict:
    return {
        "id": str(d.id),
        "status": d.status,
        "channel": d.channel,
        "title": d.title,
        "recipient_email": d.recipient_email,
        "deliverable_url": d.deliverable_url,
        "sent_at": d.sent_at.isoformat() if d.sent_at else None,
        "followup_scheduled_at": d.followup_scheduled_at.isoformat()
        if d.followup_scheduled_at else None,
        "created_at": d.created_at.isoformat(),
    }


def _parse_uuid(val: str) -> uuid.UUID:
    try:
        return uuid.UUID(val)
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid id")


async def _require_owned_job(db, job_id: str, org_id: uuid.UUID) -> ProductionJob:
    jid = _parse_uuid(job_id)
    job = (
        await db.execute(
            select(ProductionJob).where(ProductionJob.id == jid)
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "Production job not found")
    if job.org_id != org_id:
        raise HTTPException(403, "Job belongs to another organization")
    return job
