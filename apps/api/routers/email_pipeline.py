"""Email Pipeline Router — inbox connections, threads, messages, classifications, reply drafts.

Provides visibility into the Phase 1 revenue machine email system.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, func, select

from apps.api.deps import DBSession, OperatorUser
from packages.db.models.email_pipeline import (
    EmailClassification,
    EmailMessage,
    EmailReplyDraft,
    EmailThread,
    InboxConnection,
    SalesStageTransition,
)

router = APIRouter(prefix="/email-pipeline", tags=["email-pipeline"])


# ── Inbox connections ─────────────────────────────────────────────────────


@router.get("/connections")
async def list_connections(db: DBSession):
    """List all inbox connections with sync status."""
    rows = (await db.execute(
        select(InboxConnection).where(InboxConnection.is_active.is_(True))
        .order_by(desc(InboxConnection.last_sync_at))
    )).scalars().all()

    return [
        {
            "id": str(c.id),
            "email": c.email_address,
            "provider": c.provider,
            "status": c.status,
            "last_sync": c.last_sync_at.isoformat() if c.last_sync_at else None,
            "messages_synced": c.messages_synced_total,
            "consecutive_failures": c.consecutive_failures,
            "last_error": c.last_error,
        }
        for c in rows
    ]


class CreateConnectionRequest(BaseModel):
    email_address: str
    host: str = ""
    port: int = 993
    provider: str = "imap"
    org_id: str


@router.post("/connections")
async def create_connection(body: CreateConnectionRequest, db: DBSession):
    """Create a new inbox connection."""
    conn = InboxConnection(
        org_id=uuid.UUID(body.org_id),
        email_address=body.email_address,
        host=body.host,
        port=body.port,
        provider=body.provider,
        status="active",
    )
    db.add(conn)
    await db.commit()
    return {"id": str(conn.id), "status": "created"}


# ── Threads ───────────────────────────────────────────────────────────────


@router.get("/threads")
async def list_threads(
    db: DBSession,
    sales_stage: str | None = None,
    classification: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List email threads with filtering by sales stage and classification."""
    q = select(EmailThread).where(EmailThread.is_active.is_(True))

    if sales_stage:
        q = q.where(EmailThread.sales_stage == sales_stage)
    if classification:
        q = q.where(EmailThread.latest_classification == classification)

    q = q.order_by(desc(EmailThread.last_message_at)).offset(offset).limit(limit)
    rows = (await db.execute(q)).scalars().all()

    return [
        {
            "id": str(t.id),
            "subject": t.subject,
            "from_email": t.from_email,
            "from_name": t.from_name,
            "sales_stage": t.sales_stage,
            "classification": t.latest_classification,
            "reply_status": t.reply_status,
            "message_count": t.message_count,
            "direction": t.direction,
            "first_message": t.first_message_at.isoformat() if t.first_message_at else None,
            "last_message": t.last_message_at.isoformat() if t.last_message_at else None,
            "contact_id": str(t.contact_id) if t.contact_id else None,
            "lead_id": str(t.lead_opportunity_id) if t.lead_opportunity_id else None,
        }
        for t in rows
    ]


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str, db: DBSession):
    """Get a thread with all its messages and classifications."""
    thread = (await db.execute(
        select(EmailThread).where(EmailThread.id == uuid.UUID(thread_id))
    )).scalar_one_or_none()

    if not thread:
        raise HTTPException(404, "Thread not found")

    messages = (await db.execute(
        select(EmailMessage).where(EmailMessage.thread_id == thread.id)
        .order_by(EmailMessage.message_date)
    )).scalars().all()

    classifications = (await db.execute(
        select(EmailClassification).where(EmailClassification.thread_id == thread.id)
        .order_by(desc(EmailClassification.created_at))
    )).scalars().all()

    drafts = (await db.execute(
        select(EmailReplyDraft).where(EmailReplyDraft.thread_id == thread.id)
        .order_by(desc(EmailReplyDraft.created_at))
    )).scalars().all()

    return {
        "thread": {
            "id": str(thread.id),
            "subject": thread.subject,
            "sales_stage": thread.sales_stage,
            "classification": thread.latest_classification,
            "reply_status": thread.reply_status,
            "from_email": thread.from_email,
            "message_count": thread.message_count,
        },
        "messages": [
            {
                "id": str(m.id),
                "direction": m.direction,
                "from_email": m.from_email,
                "subject": m.subject,
                "snippet": m.snippet,
                "body_text": m.body_text,
                "date": m.message_date.isoformat() if m.message_date else None,
            }
            for m in messages
        ],
        "classifications": [
            {
                "id": str(c.id),
                "intent": c.intent,
                "confidence": c.confidence,
                "rationale": c.rationale,
                "reply_mode": c.reply_mode,
            }
            for c in classifications
        ],
        "drafts": [
            {
                "id": str(d.id),
                "reply_mode": d.reply_mode,
                "status": d.status,
                "subject": d.subject,
                "body_text": d.body_text[:300],
                "confidence": d.confidence,
                "package_offered": d.package_offered,
            }
            for d in drafts
        ],
    }


# ── Reply drafts ──────────────────────────────────────────────────────────


@router.get("/drafts")
async def list_drafts(
    current_user: OperatorUser,
    db: DBSession,
    status: str = "pending",
    limit: int = 50,
):
    """List reply drafts by status (pending, approved, sent, rejected).

    Org-scoped: operators only see their own organization's drafts. The
    ``intent`` field is pulled from the linked EmailClassification row,
    not from ``reasoning`` (which holds the full decision trace JSON).
    """
    rows = (
        await db.execute(
            select(EmailReplyDraft, EmailClassification)
            .outerjoin(
                EmailClassification,
                EmailClassification.id == EmailReplyDraft.classification_id,
            )
            .where(
                EmailReplyDraft.org_id == current_user.organization_id,
                EmailReplyDraft.status == status,
                EmailReplyDraft.is_active.is_(True),
            )
            .order_by(desc(EmailReplyDraft.created_at))
            .limit(limit)
        )
    ).all()

    return [
        {
            "id": str(d.id),
            "to_email": d.to_email,
            "subject": d.subject,
            "body_preview": (d.body_text or "")[:200],
            "reply_mode": d.reply_mode,
            "status": d.status,
            "confidence": d.confidence,
            "intent": classification.intent if classification is not None else None,
            "classification_confidence": (
                classification.confidence if classification is not None else None
            ),
            "mode_source": (
                d.decision_trace.get("mode_source")
                if isinstance(d.decision_trace, dict)
                else None
            ),
            "package_offered": d.package_offered,
            "approved_by": d.approved_by,
            "created_at": d.created_at.isoformat(),
        }
        for d, classification in rows
    ]


@router.post("/drafts/{draft_id}/approve")
async def approve_draft(
    draft_id: str,
    current_user: OperatorUser,
    db: DBSession,
):
    """Approve a pending draft for sending.

    Attribution, events, and operator-action audit are handled by the
    shared ``reply_draft_actions.approve_draft`` service.
    """
    from apps.api.services.reply_draft_actions import DraftActionError
    from apps.api.services.reply_draft_actions import approve_draft as approve_svc

    try:
        draft = await approve_svc(
            db, draft_id=uuid.UUID(draft_id), actor=current_user
        )
    except DraftActionError as exc:
        if exc.current_status == "missing":
            raise HTTPException(404, "Draft not found")
        raise HTTPException(400, str(exc))

    if draft.org_id != current_user.organization_id:
        raise HTTPException(403, "Draft belongs to another organization")

    await db.commit()
    return {
        "id": str(draft.id),
        "status": draft.status,
        "approved_by": draft.approved_by,
        "approved_at": draft.approved_at.isoformat() if draft.approved_at else None,
    }


class RejectDraftBody(BaseModel):
    reason: str | None = None


@router.post("/drafts/{draft_id}/reject")
async def reject_draft(
    draft_id: str,
    current_user: OperatorUser,
    db: DBSession,
    body: RejectDraftBody | None = None,
):
    """Reject a pending or approved draft so the send worker skips it."""
    from apps.api.services.reply_draft_actions import DraftActionError
    from apps.api.services.reply_draft_actions import reject_draft as reject_svc

    reason = body.reason if body else None
    try:
        draft = await reject_svc(
            db,
            draft_id=uuid.UUID(draft_id),
            actor=current_user,
            reason=reason,
        )
    except DraftActionError as exc:
        if exc.current_status == "missing":
            raise HTTPException(404, "Draft not found")
        raise HTTPException(400, str(exc))

    if draft.org_id != current_user.organization_id:
        raise HTTPException(403, "Draft belongs to another organization")

    await db.commit()
    return {"id": str(draft.id), "status": draft.status}


# ── Pipeline summary ──────────────────────────────────────────────────────


@router.get("/summary")
async def pipeline_summary(db: DBSession):
    """Dashboard summary: thread counts by sales stage + recent activity."""
    stage_counts = (await db.execute(
        select(
            EmailThread.sales_stage,
            func.count(EmailThread.id),
        ).where(EmailThread.is_active.is_(True))
        .group_by(EmailThread.sales_stage)
    )).all()

    pending_drafts = (await db.execute(
        select(func.count(EmailReplyDraft.id)).where(
            EmailReplyDraft.status == "pending",
            EmailReplyDraft.is_active.is_(True),
        )
    )).scalar()

    recent_transitions = (await db.execute(
        select(SalesStageTransition)
        .order_by(desc(SalesStageTransition.created_at))
        .limit(10)
    )).scalars().all()

    return {
        "pipeline": {stage: count for stage, count in stage_counts},
        "pending_drafts": pending_drafts,
        "recent_transitions": [
            {
                "from": t.from_stage,
                "to": t.to_stage,
                "trigger": t.trigger_type,
                "rationale": t.rationale,
                "at": t.created_at.isoformat(),
            }
            for t in recent_transitions
        ],
    }
