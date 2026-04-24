"""Shared approve/reject logic for EmailReplyDraft rows.

Both the JSON API (``/email-pipeline/drafts/{id}/approve|reject``) and
the operator-console HTML form POSTs (``/operator/drafts/{id}/...``)
call into this module, so the event + audit side-effects fire exactly
once and are identical across surfaces.

Each call:
  1. loads the draft
  2. validates the current status is actionable
  3. transitions status + records actor attribution
  4. emits a ``revenue_event`` (reply.draft.approved | .rejected)
  5. writes an OperatorAction row (auditable trail of who did what)

No schema changes — rejection metadata rides in the existing
``decision_trace`` JSONB rather than introducing new columns.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_action, emit_event
from packages.db.models.core import User
from packages.db.models.email_pipeline import EmailReplyDraft

logger = structlog.get_logger()


class DraftActionError(Exception):
    """Raised when a state transition is not permitted."""

    def __init__(self, message: str, current_status: str):
        super().__init__(message)
        self.current_status = current_status


async def approve_draft(
    db: AsyncSession,
    *,
    draft_id: uuid.UUID,
    actor: User,
) -> EmailReplyDraft:
    """Approve a pending draft for sending. Only 'pending' is valid entry state.

    Side-effects: flips status to 'approved', sets approved_by + approved_at,
    emits revenue_event, writes OperatorAction.
    """
    draft = await _load_active_draft(db, draft_id)

    if draft.status != "pending":
        raise DraftActionError(
            f"draft is {draft.status}, not pending", current_status=draft.status
        )

    now = datetime.now(timezone.utc)
    prior_status = draft.status
    draft.status = "approved"
    draft.approved_by = (actor.email or str(actor.id))[:255]
    draft.approved_at = now
    await db.flush()

    await emit_event(
        db,
        domain="monetization",
        event_type="reply.draft.approved",
        summary=f"Reply draft approved by {actor.email}",
        org_id=draft.org_id,
        entity_type="email_reply_draft",
        entity_id=draft.id,
        previous_state=prior_status,
        new_state="approved",
        actor_type="operator",
        actor_id=str(actor.id),
        details={
            "draft_id": str(draft.id),
            "thread_id": str(draft.thread_id),
            "to_email": draft.to_email,
            "reply_mode": draft.reply_mode,
            "approved_by": draft.approved_by,
        },
    )
    await emit_action(
        db,
        org_id=draft.org_id,
        action_type="reply_draft_approved",
        title=f"Approved draft to {draft.to_email[:60]}",
        description=f"Operator {actor.email} approved reply draft {draft.id}",
        category="monetization",
        priority="medium",
        entity_type="email_reply_draft",
        entity_id=draft.id,
        source_module="reply_draft_actions",
        action_payload={
            "draft_id": str(draft.id),
            "approved_by": draft.approved_by,
            "reply_mode": draft.reply_mode,
        },
    )
    logger.info(
        "reply_draft.approved",
        draft_id=str(draft.id),
        org_id=str(draft.org_id),
        approver=draft.approved_by,
        reply_mode=draft.reply_mode,
    )
    return draft


async def reject_draft(
    db: AsyncSession,
    *,
    draft_id: uuid.UUID,
    actor: User,
    reason: Optional[str] = None,
) -> EmailReplyDraft:
    """Reject a draft so the send worker never picks it up.

    Allowed entry states: pending, approved. Already-sent or already-rejected
    drafts raise DraftActionError (prevents accidental double-writes).
    """
    draft = await _load_active_draft(db, draft_id)

    if draft.status not in ("pending", "approved"):
        raise DraftActionError(
            f"draft is {draft.status}, cannot reject", current_status=draft.status
        )

    now = datetime.now(timezone.utc)
    prior_status = draft.status
    draft.status = "rejected"
    # No rejected_by column — stash actor info in decision_trace so every
    # future read shows who rejected it and why, without a schema change.
    existing_trace = draft.decision_trace if isinstance(draft.decision_trace, dict) else {}
    draft.decision_trace = {
        **existing_trace,
        "rejected_by": actor.email or str(actor.id),
        "rejected_at": now.isoformat(),
        "rejection_reason": (reason or "")[:500],
    }
    await db.flush()

    await emit_event(
        db,
        domain="monetization",
        event_type="reply.draft.rejected",
        summary=f"Reply draft rejected by {actor.email}",
        org_id=draft.org_id,
        entity_type="email_reply_draft",
        entity_id=draft.id,
        previous_state=prior_status,
        new_state="rejected",
        actor_type="operator",
        actor_id=str(actor.id),
        severity="warning",
        details={
            "draft_id": str(draft.id),
            "thread_id": str(draft.thread_id),
            "to_email": draft.to_email,
            "rejected_by": actor.email,
            "rejection_reason": reason or "",
        },
    )
    await emit_action(
        db,
        org_id=draft.org_id,
        action_type="reply_draft_rejected",
        title=f"Rejected draft to {draft.to_email[:60]}",
        description=f"Operator {actor.email} rejected reply draft {draft.id}. Reason: {reason or '(none)'}",
        category="monetization",
        priority="low",
        entity_type="email_reply_draft",
        entity_id=draft.id,
        source_module="reply_draft_actions",
        action_payload={
            "draft_id": str(draft.id),
            "rejected_by": actor.email,
            "rejection_reason": reason or "",
        },
    )
    logger.info(
        "reply_draft.rejected",
        draft_id=str(draft.id),
        org_id=str(draft.org_id),
        rejector=actor.email,
    )
    return draft


async def _load_active_draft(db: AsyncSession, draft_id: uuid.UUID) -> EmailReplyDraft:
    draft = (
        await db.execute(
            select(EmailReplyDraft).where(EmailReplyDraft.id == draft_id)
        )
    ).scalar_one_or_none()
    if draft is None or not draft.is_active:
        raise DraftActionError("draft not found", current_status="missing")
    return draft
