"""Clients + intake router (Batch 3B).

Operator-facing endpoints for the fulfillment-side client record plus
the public intake form endpoints (authenticated by unguessable token).
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import desc, select

from apps.api.deps import DBSession, OperatorUser
from apps.api.services.client_activation import (
    DEFAULT_INTAKE_SCHEMA,
    start_onboarding,
    submit_intake,
)
from packages.db.models.clients import (
    Client,
    ClientOnboardingEvent,
    IntakeRequest,
    IntakeSubmission,
)

logger = structlog.get_logger()

# ── Clients (operator-facing) ───────────────────────────────────────────────

clients_router = APIRouter(prefix="/clients", tags=["Clients"])


@clients_router.get("")
async def list_clients(
    current_user: OperatorUser,
    db: DBSession,
    status: Optional[str] = None,
    limit: int = 50,
):
    q = select(Client).where(
        Client.org_id == current_user.organization_id,
        Client.is_active.is_(True),
    )
    if status:
        q = q.where(Client.status == status)
    q = q.order_by(desc(Client.created_at)).limit(max(1, min(200, limit)))
    rows = (await db.execute(q)).scalars().all()
    return [_client_summary(c) for c in rows]


@clients_router.get("/{client_id}")
async def get_client(
    client_id: str,
    current_user: OperatorUser,
    db: DBSession,
):
    cid = _parse_uuid(client_id)
    client = await _require_owned_client(db, cid, current_user.organization_id)

    events = (
        await db.execute(
            select(ClientOnboardingEvent)
            .where(ClientOnboardingEvent.client_id == client.id)
            .order_by(desc(ClientOnboardingEvent.created_at))
        )
    ).scalars().all()

    intakes = (
        await db.execute(
            select(IntakeRequest)
            .where(IntakeRequest.client_id == client.id)
            .order_by(desc(IntakeRequest.created_at))
        )
    ).scalars().all()

    submissions = (
        await db.execute(
            select(IntakeSubmission)
            .where(IntakeSubmission.client_id == client.id)
            .order_by(desc(IntakeSubmission.created_at))
        )
    ).scalars().all()

    return {
        **_client_summary(client),
        "notes": client.notes,
        "onboarding_events": [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "created_at": e.created_at.isoformat(),
                "intake_request_id": str(e.intake_request_id) if e.intake_request_id else None,
                "intake_submission_id": str(e.intake_submission_id) if e.intake_submission_id else None,
                "actor_type": e.actor_type,
                "details": e.details_json,
            }
            for e in events
        ],
        "intake_requests": [
            {
                "id": str(r.id),
                "status": r.status,
                "title": r.title,
                "token": r.token,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "reminder_count": r.reminder_count,
            }
            for r in intakes
        ],
        "intake_submissions": [
            {
                "id": str(s.id),
                "intake_request_id": str(s.intake_request_id),
                "is_complete": s.is_complete,
                "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
                "submitter_email": s.submitter_email,
                "missing_fields": s.missing_fields_json,
            }
            for s in submissions
        ],
    }


class StartOnboardingBody(BaseModel):
    title: Optional[str] = None
    instructions: Optional[str] = None
    schema_json: Optional[dict] = None


@clients_router.post("/{client_id}/start-onboarding", status_code=201)
async def start_client_onboarding(
    client_id: str,
    body: StartOnboardingBody,
    current_user: OperatorUser,
    db: DBSession,
):
    cid = _parse_uuid(client_id)
    client = await _require_owned_client(db, cid, current_user.organization_id)
    intake = await start_onboarding(
        db,
        client=client,
        title=body.title,
        instructions=body.instructions,
        schema=body.schema_json,
    )
    await db.commit()
    return _intake_request_summary(intake)


# ── Intake (operator list + public form endpoints) ──────────────────────────

intake_router = APIRouter(tags=["Intake"])


@intake_router.get("/intake-requests")
async def list_intake_requests(
    current_user: OperatorUser,
    db: DBSession,
    status: Optional[str] = None,
    limit: int = 50,
):
    q = select(IntakeRequest).where(
        IntakeRequest.org_id == current_user.organization_id,
        IntakeRequest.is_active.is_(True),
    )
    if status:
        q = q.where(IntakeRequest.status == status)
    q = q.order_by(desc(IntakeRequest.created_at)).limit(max(1, min(200, limit)))
    rows = (await db.execute(q)).scalars().all()
    return [_intake_request_summary(r) for r in rows]


@intake_router.get("/intake/{token}")
async def public_view_intake(token: str, db: DBSession):
    """Public form-viewer keyed by token. Sets first_viewed_at on first view."""
    intake = (
        await db.execute(
            select(IntakeRequest).where(
                IntakeRequest.token == token,
                IntakeRequest.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if intake is None:
        raise HTTPException(404, "Intake not found")

    if intake.first_viewed_at is None:
        from datetime import datetime, timezone
        intake.first_viewed_at = datetime.now(timezone.utc)
        if intake.status == "sent":
            intake.status = "viewed"
        await db.commit()

    return {
        "id": str(intake.id),
        "status": intake.status,
        "title": intake.title,
        "instructions": intake.instructions,
        "schema": intake.schema_json or DEFAULT_INTAKE_SCHEMA,
        "completed": intake.status == "completed",
    }


class IntakeSubmitBody(BaseModel):
    responses: dict
    submitter_email: Optional[str] = None


@intake_router.post("/intake/{token}/submit", status_code=201)
async def public_submit_intake(
    token: str,
    body: IntakeSubmitBody,
    request: Request,
    db: DBSession,
):
    intake = (
        await db.execute(
            select(IntakeRequest).where(
                IntakeRequest.token == token,
                IntakeRequest.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if intake is None:
        raise HTTPException(404, "Intake not found")
    if intake.status == "completed":
        raise HTTPException(400, "Intake already completed")

    submitter_ip = request.client.host if request.client else None
    submission = await submit_intake(
        db,
        intake_request=intake,
        responses=body.responses or {},
        submitter_email=body.submitter_email or "",
        submitter_ip=submitter_ip,
        submitted_via="form",
    )
    await db.commit()
    return {
        "id": str(submission.id),
        "intake_request_id": str(submission.intake_request_id),
        "is_complete": submission.is_complete,
        "missing_fields": (submission.missing_fields_json or {}).get("missing", []),
        "intake_status": intake.status,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _client_summary(c: Client) -> dict:
    return {
        "id": str(c.id),
        "status": c.status,
        "primary_email": c.primary_email,
        "display_name": c.display_name,
        "company_name": c.company_name,
        "activated_at": c.activated_at.isoformat() if c.activated_at else None,
        "last_paid_at": c.last_paid_at.isoformat() if c.last_paid_at else None,
        "total_paid_cents": c.total_paid_cents,
        "first_proposal_id": str(c.first_proposal_id) if c.first_proposal_id else None,
        "first_payment_id": str(c.first_payment_id) if c.first_payment_id else None,
        "created_at": c.created_at.isoformat(),
    }


def _intake_request_summary(r: IntakeRequest) -> dict:
    return {
        "id": str(r.id),
        "client_id": str(r.client_id),
        "status": r.status,
        "token": r.token,
        "title": r.title,
        "sent_at": r.sent_at.isoformat() if r.sent_at else None,
        "first_viewed_at": r.first_viewed_at.isoformat() if r.first_viewed_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "reminder_count": r.reminder_count,
    }


def _parse_uuid(val: str) -> uuid.UUID:
    try:
        return uuid.UUID(val)
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid id")


async def _require_owned_client(db, client_id: uuid.UUID, org_id: uuid.UUID) -> Client:
    client = (
        await db.execute(
            select(Client).where(Client.id == client_id, Client.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(404, "Client not found")
    if client.org_id != org_id:
        raise HTTPException(403, "Client belongs to another organization")
    return client
