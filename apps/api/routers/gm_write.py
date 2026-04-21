"""GM write-authority router (Batch 7B).

Ten write endpoints that move GM from observer to operator. Every
endpoint:

  - requires OperatorUser auth
  - is org-scoped against current_user.organization_id (403 on cross-org)
  - wraps exactly one canonical service function
  - calls classify_action on the intent, refuses ESCALATE class
  - writes an OperatorAction audit row + emits a gm.write.<tool> event
  - returns a structured JSON response

No business logic is duplicated here — every business rule lives in the
wrapped canonical service (reply_draft_actions, proposals_service,
stage_controller, stripe_billing_service).

Endpoints:

  POST /api/v1/gm/write/approvals/{id}/approve
  POST /api/v1/gm/write/approvals/{id}/reject
  POST /api/v1/gm/write/escalations/{id}/resolve
  POST /api/v1/gm/write/drafts/{id}/approve
  POST /api/v1/gm/write/drafts/{id}/reject
  POST /api/v1/gm/write/proposals
  POST /api/v1/gm/write/proposals/{id}/send
  POST /api/v1/gm/write/proposals/{id}/payment-link
  POST /api/v1/gm/write/avenues/{avenue_id}/activate
  POST /api/v1/gm/write/stages/mark
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from apps.api.deps import DBSession, OperatorUser
from apps.api.services.gm_doctrine import (
    ACTION_CLASS_APPROVAL,
    ACTION_CLASS_AUTO,
    ACTION_CLASS_ESCALATE,
    REVENUE_AVENUES,
    STATUS_DISABLED_BY_OPERATOR,
    classify_action,
)
from apps.api.services.gm_write_service import (
    audit_gm_write,
    forbid_escalation_as_mutation,
)
from packages.db.models.email_pipeline import EmailReplyDraft
from packages.db.models.gm_control import GMApproval, GMEscalation
from packages.db.models.proposals import Payment, PaymentLink, Proposal

logger = structlog.get_logger()

router = APIRouter(prefix="/gm/write", tags=["GM Write Authority"])


# ═══════════════════════════════════════════════════════════════════════════
#  1. Approve / reject GM approvals
# ═══════════════════════════════════════════════════════════════════════════


class ApprovalDecisionBody(BaseModel):
    notes: Optional[str] = None


@router.post("/approvals/{approval_id}/approve")
async def approve_approval(
    approval_id: str,
    body: ApprovalDecisionBody,
    current_user: OperatorUser,
    db: DBSession,
):
    """Approve a pending GMApproval. Operator IS exercising authority."""
    from apps.api.services.stage_controller import resolve_approval

    approval = await _require_owned_approval(db, approval_id, current_user.organization_id)
    action_class = classify_action(
        confidence=1.0, money_involved=(approval.risk_level in ("high", "critical")),
    )
    forbid_escalation_as_mutation(
        tool_name="approvals.approve", action_class=action_class,
    )
    try:
        result = await resolve_approval(
            db, approval=approval, decision="approved",
            decided_by=current_user.email or str(current_user.id),
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    await audit_gm_write(
        db, actor=current_user, tool_name="approvals.approve",
        entity_type="gm_approval", entity_id=result.id,
        decision="executed", action_class=action_class,
        details={"notes": body.notes, "risk_level": approval.risk_level},
    )
    await db.commit()
    return {
        "approval_id": str(result.id),
        "status": result.status,
        "decided_by": result.decided_by,
        "decided_at": result.decided_at.isoformat() if result.decided_at else None,
        "action_class": action_class,
    }


@router.post("/approvals/{approval_id}/reject")
async def reject_approval(
    approval_id: str,
    body: ApprovalDecisionBody,
    current_user: OperatorUser,
    db: DBSession,
):
    from apps.api.services.stage_controller import resolve_approval

    approval = await _require_owned_approval(db, approval_id, current_user.organization_id)
    action_class = classify_action(confidence=1.0)
    forbid_escalation_as_mutation(tool_name="approvals.reject", action_class=action_class)
    try:
        result = await resolve_approval(
            db, approval=approval, decision="rejected",
            decided_by=current_user.email or str(current_user.id),
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    await audit_gm_write(
        db, actor=current_user, tool_name="approvals.reject",
        entity_type="gm_approval", entity_id=result.id,
        decision="executed", action_class=action_class,
        details={"notes": body.notes},
    )
    await db.commit()
    return {
        "approval_id": str(result.id),
        "status": result.status,
        "decided_by": result.decided_by,
        "action_class": action_class,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  2. Resolve GM escalations
# ═══════════════════════════════════════════════════════════════════════════


class EscalationResolveBody(BaseModel):
    notes: Optional[str] = None


@router.post("/escalations/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: str,
    body: EscalationResolveBody,
    current_user: OperatorUser,
    db: DBSession,
):
    from apps.api.services.stage_controller import resolve_escalation as svc

    escalation = await _require_owned_escalation(
        db, escalation_id, current_user.organization_id
    )
    action_class = classify_action(confidence=1.0)
    forbid_escalation_as_mutation(
        tool_name="escalations.resolve", action_class=action_class,
    )
    result = await svc(
        db, escalation=escalation,
        resolved_by=current_user.email or str(current_user.id),
        notes=body.notes,
    )
    await audit_gm_write(
        db, actor=current_user, tool_name="escalations.resolve",
        entity_type="gm_escalation", entity_id=result.id,
        decision="executed", action_class=action_class,
        details={"notes": body.notes, "reason_code": escalation.reason_code},
    )
    await db.commit()
    return {
        "escalation_id": str(result.id),
        "status": result.status,
        "resolved_at": result.resolved_at.isoformat() if result.resolved_at else None,
        "action_class": action_class,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  3. Approve / reject reply drafts
# ═══════════════════════════════════════════════════════════════════════════


class DraftDecisionBody(BaseModel):
    reason: Optional[str] = None


@router.post("/drafts/{draft_id}/approve")
async def approve_draft(
    draft_id: str,
    current_user: OperatorUser,
    db: DBSession,
):
    from apps.api.services.reply_draft_actions import (
        DraftActionError, approve_draft as svc,
    )

    did = _parse_uuid(draft_id)
    action_class = classify_action(confidence=1.0, money_involved=True)
    forbid_escalation_as_mutation(
        tool_name="drafts.approve", action_class=action_class,
    )
    try:
        draft = await svc(db, draft_id=did, actor=current_user)
    except DraftActionError as exc:
        if exc.current_status == "missing":
            raise HTTPException(404, "Draft not found")
        raise HTTPException(400, str(exc))

    if draft.org_id != current_user.organization_id:
        raise HTTPException(403, "Draft belongs to another organization")

    await audit_gm_write(
        db, actor=current_user, tool_name="drafts.approve",
        entity_type="email_reply_draft", entity_id=draft.id,
        decision="executed", action_class=action_class,
        details={"reply_mode": draft.reply_mode, "to_email": draft.to_email},
    )
    await db.commit()
    return {
        "draft_id": str(draft.id),
        "status": draft.status,
        "approved_by": draft.approved_by,
        "action_class": action_class,
    }


@router.post("/drafts/{draft_id}/reject")
async def reject_draft(
    draft_id: str,
    body: DraftDecisionBody,
    current_user: OperatorUser,
    db: DBSession,
):
    from apps.api.services.reply_draft_actions import (
        DraftActionError, reject_draft as svc,
    )

    did = _parse_uuid(draft_id)
    action_class = classify_action(confidence=1.0)
    forbid_escalation_as_mutation(
        tool_name="drafts.reject", action_class=action_class,
    )
    try:
        draft = await svc(db, draft_id=did, actor=current_user, reason=body.reason)
    except DraftActionError as exc:
        if exc.current_status == "missing":
            raise HTTPException(404, "Draft not found")
        raise HTTPException(400, str(exc))

    if draft.org_id != current_user.organization_id:
        raise HTTPException(403, "Draft belongs to another organization")

    await audit_gm_write(
        db, actor=current_user, tool_name="drafts.reject",
        entity_type="email_reply_draft", entity_id=draft.id,
        decision="executed", action_class=action_class,
        details={"reason": body.reason},
    )
    await db.commit()
    return {
        "draft_id": str(draft.id),
        "status": draft.status,
        "action_class": action_class,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  4. Create proposal
# ═══════════════════════════════════════════════════════════════════════════


class ProposalLineItemBody(BaseModel):
    description: str = Field(..., max_length=500)
    unit_amount_cents: int = Field(..., ge=0)
    quantity: int = Field(1, ge=1)
    offer_id: Optional[uuid.UUID] = None
    package_slug: Optional[str] = Field(None, max_length=100)
    currency: str = "usd"
    position: int = 0


class CreateProposalBody(BaseModel):
    recipient_email: str = Field(..., max_length=255)
    title: str = Field(..., max_length=500)
    line_items: list[ProposalLineItemBody] = Field(..., min_length=1)
    brand_id: Optional[uuid.UUID] = None
    recipient_name: str = ""
    recipient_company: str = ""
    summary: str = ""
    package_slug: Optional[str] = None
    currency: str = "usd"
    notes: Optional[str] = None


@router.post("/proposals", status_code=201)
async def create_proposal(
    body: CreateProposalBody,
    current_user: OperatorUser,
    db: DBSession,
):
    from apps.api.services.proposals_service import (
        LineItemInput, create_proposal as svc,
    )

    action_class = classify_action(confidence=1.0, money_involved=True)
    forbid_escalation_as_mutation(
        tool_name="proposals.create", action_class=action_class,
    )
    total_cents = sum(li.quantity * li.unit_amount_cents for li in body.line_items)
    proposal = await svc(
        db,
        org_id=current_user.organization_id,
        recipient_email=body.recipient_email,
        title=body.title,
        line_items=[
            LineItemInput(
                description=li.description,
                unit_amount_cents=li.unit_amount_cents,
                quantity=li.quantity,
                offer_id=li.offer_id,
                package_slug=li.package_slug,
                currency=li.currency,
                position=li.position,
            )
            for li in body.line_items
        ],
        brand_id=body.brand_id,
        recipient_name=body.recipient_name,
        recipient_company=body.recipient_company,
        summary=body.summary,
        package_slug=body.package_slug,
        currency=body.currency,
        created_by_actor_type="operator",
        created_by_actor_id=str(current_user.id),
        notes=body.notes,
    )
    await audit_gm_write(
        db, actor=current_user, tool_name="proposals.create",
        entity_type="proposal", entity_id=proposal.id,
        decision="executed", action_class=action_class,
        details={
            "recipient_email": body.recipient_email,
            "total_cents": total_cents,
            "line_item_count": len(body.line_items),
        },
    )
    await db.commit()
    return {
        "proposal_id": str(proposal.id),
        "status": proposal.status,
        "total_amount_cents": proposal.total_amount_cents,
        "recipient_email": proposal.recipient_email,
        "action_class": action_class,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  5. Send proposal
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/proposals/{proposal_id}/send")
async def send_proposal(
    proposal_id: str,
    current_user: OperatorUser,
    db: DBSession,
):
    from apps.api.services.proposals_service import mark_proposal_sent as svc

    pid = _parse_uuid(proposal_id)
    proposal = await _require_owned_proposal(db, pid, current_user.organization_id)
    action_class = classify_action(confidence=1.0, money_involved=True)
    forbid_escalation_as_mutation(
        tool_name="proposals.send", action_class=action_class,
    )
    try:
        result = await svc(
            db, proposal_id=pid, actor_type="operator",
            actor_id=str(current_user.id),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    await audit_gm_write(
        db, actor=current_user, tool_name="proposals.send",
        entity_type="proposal", entity_id=result.id,
        decision="executed", action_class=action_class,
        details={"recipient_email": result.recipient_email},
    )
    await db.commit()
    return {
        "proposal_id": str(result.id),
        "status": result.status,
        "sent_at": result.sent_at.isoformat() if result.sent_at else None,
        "action_class": action_class,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  6. Create payment link
# ═══════════════════════════════════════════════════════════════════════════


class CreatePaymentLinkBody(BaseModel):
    amount_cents: Optional[int] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=10)
    product_name: Optional[str] = Field(None, max_length=500)


@router.post("/proposals/{proposal_id}/payment-link", status_code=201)
async def create_payment_link(
    proposal_id: str,
    body: CreatePaymentLinkBody,
    current_user: OperatorUser,
    db: DBSession,
):
    from apps.api.services.proposals_service import record_payment_link
    from apps.api.services.stripe_billing_service import create_payment_link as stripe_svc

    pid = _parse_uuid(proposal_id)
    proposal = await _require_owned_proposal(db, pid, current_user.organization_id)
    action_class = classify_action(confidence=1.0, money_involved=True)
    forbid_escalation_as_mutation(
        tool_name="proposals.payment_link", action_class=action_class,
    )

    amount = body.amount_cents or proposal.total_amount_cents
    if amount <= 0:
        raise HTTPException(400, "Proposal has no total_amount_cents and no amount override")
    currency = (body.currency or proposal.currency or "usd").lower()
    product_name = body.product_name or proposal.title

    stripe_result = await stripe_svc(
        amount_cents=amount, currency=currency, product_name=product_name,
        metadata={
            "org_id": str(current_user.organization_id),
            "proposal_id": str(proposal.id),
            "brand_id": str(proposal.brand_id) if proposal.brand_id else "",
            "source": "proposal",
            "avenue": "b2b_services",
        },
        db=db, org_id=current_user.organization_id,
    )
    if stripe_result.get("error") or not stripe_result.get("url"):
        raise HTTPException(
            502,
            f"Stripe payment link creation failed: {stripe_result.get('error') or 'no url'}",
        )

    link = await record_payment_link(
        db, org_id=current_user.organization_id, proposal_id=proposal.id,
        brand_id=proposal.brand_id, url=stripe_result["url"],
        amount_cents=amount, provider="stripe",
        provider_link_id=stripe_result.get("id"), currency=currency,
        source="gm_write",
        metadata={"product_name": product_name, "actor": current_user.email},
    )

    await audit_gm_write(
        db, actor=current_user, tool_name="proposals.payment_link",
        entity_type="payment_link", entity_id=link.id,
        decision="executed", action_class=action_class,
        details={"proposal_id": str(proposal.id), "amount_cents": amount,
                  "provider_link_id": link.provider_link_id},
    )
    await db.commit()
    return {
        "payment_link_id": str(link.id),
        "proposal_id": str(proposal.id),
        "url": link.url,
        "amount_cents": link.amount_cents,
        "provider_link_id": link.provider_link_id,
        "action_class": action_class,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  7. Activate dormant avenue (policy authorization — not execution)
# ═══════════════════════════════════════════════════════════════════════════


class ActivateAvenueBody(BaseModel):
    authorization_notes: str = Field(..., min_length=1, max_length=2000)
    acknowledge_unlock_plan: bool = Field(
        True,
        description="Must be True — caller confirms they have read the doctrine unlock plan for this avenue.",
    )


@router.post("/avenues/{avenue_id}/activate", status_code=201)
async def activate_dormant_avenue(
    avenue_id: str,
    body: ActivateAvenueBody,
    current_user: OperatorUser,
    db: DBSession,
):
    """Operator authorizes activation of a LIVE_BUT_DORMANT or
    PRESENT_IN_CODE_ONLY avenue.

    This does NOT execute the unlock plan's individual steps — those
    happen via their own canonical services (create_proposal, etc.).
    This endpoint records the policy authorization: "from now on, the
    autonomous workers + GM are authorized to act on this avenue per
    its doctrine unlock plan."

    Enforces DORMANT_AVENUE_RULE: always approval_required, never auto.
    Refuses DISABLED_BY_OPERATOR avenues.
    """
    avenue = next((a for a in REVENUE_AVENUES if a["id"] == avenue_id), None)
    if avenue is None:
        raise HTTPException(404, f"Unknown avenue_id: {avenue_id}")
    if avenue["status"] == STATUS_DISABLED_BY_OPERATOR:
        raise HTTPException(
            400,
            f"Avenue {avenue_id} is DISABLED_BY_OPERATOR. "
            "Re-enable via doctrine policy before activating.",
        )
    if not body.acknowledge_unlock_plan:
        raise HTTPException(
            400, "acknowledge_unlock_plan must be true — read the unlock plan first.",
        )

    action_class = classify_action(
        confidence=1.0, activates_dormant_avenue=True, money_involved=True,
    )
    forbid_escalation_as_mutation(
        tool_name="avenues.activate", action_class=action_class,
    )

    # The activation itself is the audit row + event. No avenue_status
    # table is written; the doctrine + operator_actions row is the
    # authoritative record of operator intent.
    action_row = await audit_gm_write(
        db, actor=current_user, tool_name="avenues.activate",
        entity_type="avenue", entity_id=None,
        decision="executed", action_class=action_class,
        details={
            "avenue_id": avenue_id,
            "avenue_n": avenue["n"],
            "doctrine_status": avenue["status"],
            "display_name": avenue["display_name"],
            "authorization_notes": body.authorization_notes,
            "unlock_plan": avenue.get("unlock_plan") or [],
            "revenue_tables": avenue.get("revenue_tables", []),
            "activity_tables": avenue.get("activity_tables", []),
        },
    )
    await db.commit()
    return {
        "audit_action_id": str(action_row.id),
        "avenue_id": avenue_id,
        "avenue_n": avenue["n"],
        "display_name": avenue["display_name"],
        "doctrine_status": avenue["status"],
        "authorized_by": current_user.email,
        "authorized_at": action_row.created_at.isoformat(),
        "unlock_plan": avenue.get("unlock_plan") or [],
        "action_class": action_class,
        "next_steps": (
            "Autonomous workers + GM are now authorized to execute this "
            "avenue's unlock plan. Actual plan steps execute via their "
            "own canonical services (create_proposal, etc.)."
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  8. Mark stage (event-backed transitions only)
# ═══════════════════════════════════════════════════════════════════════════


class MarkStageBody(BaseModel):
    entity_type: str = Field(..., min_length=1, max_length=50)
    entity_id: uuid.UUID
    stage: str = Field(..., min_length=1, max_length=50)
    backing_event_id: uuid.UUID = Field(
        ...,
        description=(
            "ID of the SystemEvent row that justifies this stage "
            "transition. Required — the DORMANT rule and the "
            "no-fake-progress rule both forbid stage advancement "
            "without row-level event evidence."
        ),
    )
    notes: Optional[str] = None


@router.post("/stages/mark", status_code=201)
async def mark_stage(
    body: MarkStageBody,
    current_user: OperatorUser,
    db: DBSession,
):
    """Advance a stage_state row. REQUIRES a backing_event_id that
    belongs to the same org and is recent (<= 24h).

    Doctrine rule enforced: "Do NOT mark a stage complete without a
    row-level event to cite."
    """
    from datetime import datetime, timedelta, timezone
    from apps.api.services.stage_controller import mark_stage as svc
    from packages.db.models.system_events import SystemEvent

    event = (
        await db.execute(
            select(SystemEvent).where(SystemEvent.id == body.backing_event_id)
        )
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(
            400,
            f"backing_event_id {body.backing_event_id} not found. "
            "Stage advancement requires row-level event evidence.",
        )
    if event.organization_id != current_user.organization_id:
        raise HTTPException(403, "backing_event_id belongs to another organization")
    age = datetime.now(timezone.utc) - event.created_at
    if age > timedelta(hours=24):
        raise HTTPException(
            400,
            f"backing_event_id is {int(age.total_seconds() // 3600)}h old. "
            "Stage advancement requires a recent (<= 24h) event.",
        )

    action_class = classify_action(confidence=1.0)
    forbid_escalation_as_mutation(
        tool_name="stages.mark", action_class=action_class,
    )
    state = await svc(
        db, org_id=current_user.organization_id,
        entity_type=body.entity_type, entity_id=body.entity_id,
        stage=body.stage,
        metadata={
            "marked_by": current_user.email,
            "backing_event_id": str(body.backing_event_id),
            "backing_event_type": event.event_type,
            "notes": body.notes or "",
        },
    )
    await audit_gm_write(
        db, actor=current_user, tool_name="stages.mark",
        entity_type=body.entity_type, entity_id=body.entity_id,
        decision="executed", action_class=action_class,
        details={
            "stage": body.stage,
            "previous_stage": state.previous_stage,
            "backing_event_id": str(body.backing_event_id),
            "backing_event_type": event.event_type,
        },
    )
    await db.commit()
    return {
        "entity_type": state.entity_type,
        "entity_id": str(state.entity_id),
        "stage": state.stage,
        "previous_stage": state.previous_stage,
        "entered_at": state.entered_at.isoformat() if state.entered_at else None,
        "sla_deadline": state.sla_deadline.isoformat() if state.sla_deadline else None,
        "backing_event_id": str(body.backing_event_id),
        "action_class": action_class,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers — UUID parsing + org-scope checks
# ═══════════════════════════════════════════════════════════════════════════


def _parse_uuid(val: str) -> uuid.UUID:
    try:
        return uuid.UUID(val)
    except (ValueError, TypeError):
        raise HTTPException(400, f"Invalid UUID: {val}")


async def _require_owned_approval(
    db: DBSession, approval_id: str, org_id: uuid.UUID,
) -> GMApproval:
    aid = _parse_uuid(approval_id)
    row = (
        await db.execute(select(GMApproval).where(GMApproval.id == aid))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Approval not found")
    if row.org_id != org_id:
        raise HTTPException(403, "Approval belongs to another organization")
    return row


async def _require_owned_escalation(
    db: DBSession, escalation_id: str, org_id: uuid.UUID,
) -> GMEscalation:
    eid = _parse_uuid(escalation_id)
    row = (
        await db.execute(select(GMEscalation).where(GMEscalation.id == eid))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Escalation not found")
    if row.org_id != org_id:
        raise HTTPException(403, "Escalation belongs to another organization")
    return row


async def _require_owned_proposal(
    db: DBSession, proposal_id: uuid.UUID, org_id: uuid.UUID,
) -> Proposal:
    row = (
        await db.execute(
            select(Proposal).where(
                Proposal.id == proposal_id, Proposal.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Proposal not found")
    if row.org_id != org_id:
        raise HTTPException(403, "Proposal belongs to another organization")
    return row
