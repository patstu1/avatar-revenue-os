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
from packages.db.models.clients import Client, IntakeRequest
from packages.db.models.delivery import Delivery
from packages.db.models.email_pipeline import EmailReplyDraft
from packages.db.models.expansion_pack2_phase_c import SponsorTarget
from packages.db.models.fulfillment import ClientProject, ProductionJob, ProjectBrief
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
#  9. Batch 9 — fulfillment-chain GM write authority
# ═══════════════════════════════════════════════════════════════════════════
#
# Seven endpoints that give the operator a command surface for every
# fulfillment stage that previously depended on a silent autonomous
# worker. Each is a thin wrapper over the canonical service + audit +
# event. No new business logic lives here.
#
# Doctrine posture: all seven are APPROVAL_REQUIRED (human-in-the-loop
# actions that touch the customer, the deliverable, or money). None
# are AUTO_EXECUTE — the operator hitting the tool IS the approval.


class IntakeResendBody(BaseModel):
    note: Optional[str] = Field(None, max_length=1000)


@router.post("/intake/{intake_request_id}/resend")
async def resend_intake_invite(
    intake_request_id: str,
    body: IntakeResendBody,
    current_user: OperatorUser,
    db: DBSession,
):
    """Re-send the intake-invite email for a client. Used when the
    original invite landed in spam, the buyer lost it, or the autonomous
    send failed at ``start_onboarding`` time.

    Wraps ``client_activation.send_intake_invite(reminder=True)``.
    """
    from apps.api.services.client_activation import send_intake_invite

    iid = _parse_uuid(intake_request_id)
    intake = (
        await db.execute(select(IntakeRequest).where(IntakeRequest.id == iid))
    ).scalar_one_or_none()
    if intake is None:
        raise HTTPException(404, "Intake request not found")
    if intake.org_id != current_user.organization_id:
        raise HTTPException(403, "Intake belongs to another organization")

    client = (
        await db.execute(select(Client).where(Client.id == intake.client_id))
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(404, "Client not found for intake")

    action_class = classify_action(confidence=1.0, money_involved=False)
    forbid_escalation_as_mutation(
        tool_name="intake.resend", action_class=action_class,
    )

    result = await send_intake_invite(
        db, client=client, intake_request=intake, reminder=True,
    )
    await audit_gm_write(
        db, actor=current_user, tool_name="intake.resend",
        entity_type="intake_request", entity_id=intake.id,
        decision="executed" if result.get("success") else "failed",
        action_class=action_class,
        details={
            "client_id": str(client.id),
            "provider": result.get("provider"),
            "success": bool(result.get("success")),
            "error": result.get("error"),
            "note": body.note,
            "reminder_count": intake.reminder_count,
        },
        severity="info" if result.get("success") else "warning",
    )
    await db.commit()
    if not result.get("success"):
        raise HTTPException(
            502,
            f"Intake invite send failed: {result.get('error') or 'unknown'}",
        )
    return {
        "intake_request_id": str(intake.id),
        "client_id": str(client.id),
        "reminder_count": intake.reminder_count,
        "provider": result.get("provider"),
        "action_class": action_class,
    }


class ProductionLaunchBody(BaseModel):
    job_type: str = Field("content_pack", max_length=60)
    title: Optional[str] = Field(None, max_length=500)
    metadata: Optional[dict] = None


@router.post("/production/briefs/{brief_id}/launch", status_code=201)
async def launch_production(
    brief_id: str,
    body: ProductionLaunchBody,
    current_user: OperatorUser,
    db: DBSession,
):
    """Operator-forced launch of a ProductionJob for a given brief.
    Normally the autonomous fulfillment-worker picks jobs up, but this
    lets GM skip the queue or restart a failed job.
    """
    from apps.api.services.fulfillment_service import launch_production_for_brief

    bid = _parse_uuid(brief_id)
    brief = (
        await db.execute(select(ProjectBrief).where(ProjectBrief.id == bid))
    ).scalar_one_or_none()
    if brief is None:
        raise HTTPException(404, "Brief not found")
    if brief.org_id != current_user.organization_id:
        raise HTTPException(403, "Brief belongs to another organization")

    action_class = classify_action(confidence=1.0, money_involved=True)
    forbid_escalation_as_mutation(
        tool_name="production.launch", action_class=action_class,
    )

    job = await launch_production_for_brief(
        db, brief=brief, job_type=body.job_type, title=body.title,
        metadata=body.metadata,
    )
    await audit_gm_write(
        db, actor=current_user, tool_name="production.launch",
        entity_type="production_job", entity_id=job.id,
        decision="executed", action_class=action_class,
        details={
            "brief_id": str(brief.id),
            "project_id": str(brief.project_id),
            "job_type": body.job_type,
            "avenue_slug": job.avenue_slug,
        },
    )
    await db.commit()
    return {
        "production_job_id": str(job.id),
        "brief_id": str(brief.id),
        "status": job.status,
        "avenue_slug": job.avenue_slug,
        "action_class": action_class,
    }


class ProductionSubmitOutputBody(BaseModel):
    deliverable_url: str = Field(..., min_length=1, max_length=2000)
    notes: Optional[str] = Field(None, max_length=2000)
    auto_dispatch_delivery: bool = True


@router.post("/production/{job_id}/submit-output", status_code=201)
async def submit_production_output(
    job_id: str,
    body: ProductionSubmitOutputBody,
    current_user: OperatorUser,
    db: DBSession,
):
    """Operator hands off a completed production output. Cascades into
    QA review → delivery dispatch → follow-up scheduling via
    ``qa_delivery_service.submit_production_output`` (same canonical path
    as the autonomous worker would use)."""
    from apps.api.services.qa_delivery_service import (
        submit_production_output as svc_submit,
    )

    jid = _parse_uuid(job_id)
    job = (
        await db.execute(select(ProductionJob).where(ProductionJob.id == jid))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "Production job not found")
    if job.org_id != current_user.organization_id:
        raise HTTPException(403, "Job belongs to another organization")

    action_class = classify_action(confidence=1.0, money_involved=True)
    forbid_escalation_as_mutation(
        tool_name="production.submit_output", action_class=action_class,
    )

    result = await svc_submit(
        db, job=job, output_url=body.deliverable_url,
        auto_dispatch=body.auto_dispatch_delivery,
    )
    await audit_gm_write(
        db, actor=current_user, tool_name="production.submit_output",
        entity_type="production_job", entity_id=job.id,
        decision="executed", action_class=action_class,
        details={
            "deliverable_url": body.deliverable_url,
            "notes": body.notes,
            "avenue_slug": job.avenue_slug,
            "qa": result.get("qa"),
            "delivery": result.get("delivery"),
        },
    )
    await db.commit()
    return {
        "production_job_id": str(job.id),
        "status": job.status,
        "qa": result.get("qa"),
        "delivery": result.get("delivery"),
        "action_class": action_class,
    }


class DeliveryDispatchBody(BaseModel):
    channel: str = "email"
    subject: Optional[str] = Field(None, max_length=1000)
    message: Optional[str] = Field(None, max_length=10000)
    deliverable_url: Optional[str] = Field(None, max_length=2000)
    followup_days: int = Field(7, ge=1, le=60)


@router.post("/deliveries/dispatch/{job_id}", status_code=201)
async def force_dispatch_delivery(
    job_id: str,
    body: DeliveryDispatchBody,
    current_user: OperatorUser,
    db: DBSession,
):
    """Force-dispatch a Delivery for a production job that passed QA but
    hasn't auto-delivered, or re-send a delivery that failed to go out.
    Wraps ``qa_delivery_service.dispatch_delivery``."""
    from apps.api.services.qa_delivery_service import dispatch_delivery

    jid = _parse_uuid(job_id)
    job = (
        await db.execute(select(ProductionJob).where(ProductionJob.id == jid))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "Production job not found")
    if job.org_id != current_user.organization_id:
        raise HTTPException(403, "Job belongs to another organization")

    action_class = classify_action(confidence=1.0, money_involved=True)
    forbid_escalation_as_mutation(
        tool_name="deliveries.dispatch", action_class=action_class,
    )

    delivery = await dispatch_delivery(
        db, job=job, channel=body.channel, subject=body.subject,
        message=body.message, deliverable_url=body.deliverable_url,
        followup_days=body.followup_days,
    )
    await audit_gm_write(
        db, actor=current_user, tool_name="deliveries.dispatch",
        entity_type="delivery", entity_id=delivery.id,
        decision="executed", action_class=action_class,
        details={
            "production_job_id": str(job.id),
            "channel": body.channel,
            "followup_days": body.followup_days,
            "avenue_slug": delivery.avenue_slug,
        },
    )
    await db.commit()
    return {
        "delivery_id": str(delivery.id),
        "production_job_id": str(job.id),
        "status": delivery.status,
        "followup_scheduled_at": (
            delivery.followup_scheduled_at.isoformat()
            if delivery.followup_scheduled_at else None
        ),
        "action_class": action_class,
    }


class DeliveryFollowupBody(BaseModel):
    when_iso: Optional[str] = Field(
        None,
        description="ISO-8601 timestamp. If omitted, defaults to now + 7 days.",
    )


@router.post("/deliveries/{delivery_id}/schedule-followup")
async def schedule_delivery_followup(
    delivery_id: str,
    body: DeliveryFollowupBody,
    current_user: OperatorUser,
    db: DBSession,
):
    """Set or reset the follow-up send time on a delivery. The beat
    task dispatches followups whose time has matured."""
    from datetime import datetime, timedelta, timezone
    from apps.api.services.qa_delivery_service import schedule_followup

    did = _parse_uuid(delivery_id)
    delivery = (
        await db.execute(select(Delivery).where(Delivery.id == did))
    ).scalar_one_or_none()
    if delivery is None:
        raise HTTPException(404, "Delivery not found")
    if delivery.org_id != current_user.organization_id:
        raise HTTPException(403, "Delivery belongs to another organization")

    if body.when_iso:
        try:
            when = datetime.fromisoformat(body.when_iso.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(400, f"Invalid when_iso: {body.when_iso}")
    else:
        when = datetime.now(timezone.utc) + timedelta(days=7)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    action_class = classify_action(confidence=1.0, money_involved=False)
    forbid_escalation_as_mutation(
        tool_name="deliveries.schedule_followup", action_class=action_class,
    )

    await schedule_followup(db, delivery=delivery, when=when)
    # Reset followup_sent_at so the beat task re-dispatches.
    delivery.followup_sent_at = None
    await db.flush()

    await audit_gm_write(
        db, actor=current_user, tool_name="deliveries.schedule_followup",
        entity_type="delivery", entity_id=delivery.id,
        decision="executed", action_class=action_class,
        details={
            "followup_scheduled_at": when.isoformat(),
            "avenue_slug": delivery.avenue_slug,
        },
    )
    await db.commit()
    return {
        "delivery_id": str(delivery.id),
        "followup_scheduled_at": when.isoformat(),
        "followup_sent_at": None,
        "action_class": action_class,
    }


class DunningSendBody(BaseModel):
    note: Optional[str] = Field(None, max_length=2000)


@router.post("/proposals/{proposal_id}/dunning/send")
async def send_dunning_reminder(
    proposal_id: str,
    body: DunningSendBody,
    current_user: OperatorUser,
    db: DBSession,
):
    """Fire the next-in-sequence dunning reminder for an unpaid proposal.
    Wraps ``proposal_dunning_service.send_reminder``. Operator-commanded
    path — the beat task also fires automatically at the configured
    cadence."""
    from apps.api.services.proposal_dunning_service import send_reminder

    proposal = await _require_owned_proposal(
        db, _parse_uuid(proposal_id), current_user.organization_id
    )
    action_class = classify_action(confidence=1.0, money_involved=True)
    forbid_escalation_as_mutation(
        tool_name="proposals.dunning_send", action_class=action_class,
    )

    result = await send_reminder(
        db, proposal=proposal,
        actor_type="operator", actor_id=str(current_user.id),
    )
    await audit_gm_write(
        db, actor=current_user, tool_name="proposals.dunning_send",
        entity_type="proposal", entity_id=proposal.id,
        decision="executed" if result.get("sent") else "refused",
        action_class=action_class,
        details={
            "reminder_number": result.get("reminder_number"),
            "reason": result.get("reason"),
            "note": body.note,
            "avenue_slug": proposal.avenue_slug,
        },
        severity="info" if result.get("sent") else "warning",
    )
    await db.commit()
    return {
        "proposal_id": str(proposal.id),
        "sent": bool(result.get("sent")),
        "reminder_number": result.get("reminder_number"),
        "reason": result.get("reason"),
        "dunning_status": proposal.dunning_status,
        "action_class": action_class,
    }


class IssueClassificationBody(BaseModel):
    issue_type: str = Field(
        ...,
        pattern="^(refund|cancel|complaint|question|upsell_intent|bug|praise|other)$",
        description=(
            "refund=buyer wants money back; cancel=stop service/sub; "
            "complaint=unhappy but not requesting refund; question=just asking; "
            "upsell_intent=asking about more / bigger package; bug=technical issue; "
            "praise=positive feedback; other=anything else."
        ),
    )
    severity: str = Field("info", pattern="^(info|warning|critical)$")
    notes: Optional[str] = Field(None, max_length=4000)


@router.post("/issues/drafts/{draft_id}/classify")
async def classify_issue(
    draft_id: str,
    body: IssueClassificationBody,
    current_user: OperatorUser,
    db: DBSession,
):
    """Tag an inbound reply draft with an issue type. Creates a
    ClientOnboardingEvent (if we can resolve the originating client)
    plus a GMEscalation for ``refund`` / ``cancel`` / ``critical``
    severity so the right action queue sees it."""
    from packages.db.models.clients import ClientOnboardingEvent

    did = _parse_uuid(draft_id)
    draft = (
        await db.execute(select(EmailReplyDraft).where(EmailReplyDraft.id == did))
    ).scalar_one_or_none()
    if draft is None:
        raise HTTPException(404, "Draft not found")
    if draft.org_id != current_user.organization_id:
        raise HTTPException(403, "Draft belongs to another organization")

    action_class = classify_action(confidence=1.0, money_involved=body.issue_type in ("refund", "cancel"))
    forbid_escalation_as_mutation(
        tool_name="issues.classify", action_class=action_class,
    )

    # Best-effort find the Client for this inbound thread (by to_email).
    client = (
        await db.execute(
            select(Client).where(
                Client.org_id == draft.org_id,
                Client.primary_email == (draft.to_email or "").lower(),
            )
        )
    ).scalar_one_or_none()

    if client is not None:
        db.add(
            ClientOnboardingEvent(
                client_id=client.id,
                org_id=client.org_id,
                event_type=f"issue.{body.issue_type}",
                details_json={
                    "draft_id": str(draft.id),
                    "issue_type": body.issue_type,
                    "severity": body.severity,
                    "notes": body.notes,
                    "classified_by": current_user.email,
                },
                actor_type="operator",
                actor_id=current_user.email,
            )
        )

    # High-severity / money-touching issues → open a GMEscalation so the
    # operator queue surfaces them.
    escalation_id = None
    if body.issue_type in ("refund", "cancel") or body.severity == "critical":
        esc = GMEscalation(
            org_id=draft.org_id,
            reason_code=f"issue_{body.issue_type}",
            entity_type="email_reply_draft",
            entity_id=draft.id,
            title=f"Customer issue [{body.issue_type}]: {(draft.subject or 'reply')[:300]}",
            description=(
                body.notes
                or f"Operator-classified issue of type {body.issue_type} from "
                f"{draft.to_email}. Decide outcome: refund / cancel / respond."
            )[:4000],
            severity=body.severity if body.severity != "info" else "warning",
            status="open",
            details_json={
                "draft_id": str(draft.id),
                "client_id": str(client.id) if client else None,
                "issue_type": body.issue_type,
                "to_email": draft.to_email,
            },
        )
        db.add(esc)
        await db.flush()
        escalation_id = esc.id

    await audit_gm_write(
        db, actor=current_user, tool_name="issues.classify",
        entity_type="email_reply_draft", entity_id=draft.id,
        decision="executed", action_class=action_class,
        details={
            "issue_type": body.issue_type,
            "severity": body.severity,
            "client_id": str(client.id) if client else None,
            "escalation_id": str(escalation_id) if escalation_id else None,
        },
        severity=body.severity if body.severity != "info" else "info",
    )
    await db.commit()
    return {
        "draft_id": str(draft.id),
        "issue_type": body.issue_type,
        "severity": body.severity,
        "client_id": str(client.id) if client else None,
        "escalation_id": str(escalation_id) if escalation_id else None,
        "action_class": action_class,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  10. Batch 10 — front-of-funnel GM write authority
# ═══════════════════════════════════════════════════════════════════════════
#
# Seven endpoints that give GM command surface over the pre-payment
# half of the customer circle: lead import, qualification, outreach,
# reply control, and the hand-off to the already-live proposal path.


class LeadRowBody(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    instagram_handle: Optional[str] = None
    website_url: Optional[str] = None
    industry: Optional[str] = None
    niche_tag: Optional[str] = None
    estimated_size: Optional[str] = None
    estimated_deal_value: Optional[float] = None
    fit_score: Optional[float] = None
    confidence: Optional[float] = None
    notes: Optional[str] = None


class LeadImportBody(BaseModel):
    avenue_slug: str = Field(..., min_length=1, max_length=60)
    rows: list[LeadRowBody] = Field(..., min_length=1, max_length=500)
    csv: Optional[str] = Field(
        None, description="Optional raw CSV. If present, rows+csv are merged.",
        max_length=500_000,
    )


@router.post("/leads/import", status_code=201)
async def gm_leads_import(
    body: LeadImportBody,
    current_user: OperatorUser,
    db: DBSession,
):
    """Bulk-import leads (``sponsor_targets``) and tag each with
    ``avenue_slug``. Wraps ``gm_front_of_funnel_service.bulk_import_leads_with_avenue``."""
    from apps.api.services.gm_front_of_funnel_service import (
        bulk_import_leads_with_avenue, parse_csv_rows,
    )

    rows = [r.model_dump(exclude_none=False) for r in body.rows]
    if body.csv:
        csv_rows = await parse_csv_rows(body.csv)
        rows.extend(csv_rows)

    action_class = classify_action(confidence=1.0, money_involved=True)
    forbid_escalation_as_mutation(
        tool_name="leads.import", action_class=action_class,
    )
    try:
        result = await bulk_import_leads_with_avenue(
            db,
            org_id=current_user.organization_id,
            avenue_slug=body.avenue_slug,
            rows=rows,
            source=f"gm_write.leads.import:{current_user.email}",
        )
    except ValueError as ve:
        raise HTTPException(400, str(ve))

    await audit_gm_write(
        db, actor=current_user, tool_name="leads.import",
        entity_type="brand", entity_id=None,
        decision="executed", action_class=action_class,
        details={
            "avenue_slug": body.avenue_slug,
            "imported": result["imported"],
            "skipped": result["skipped"],
            "first_lead_id": result["first_lead_id"],
        },
    )
    await db.commit()
    return {**result, "avenue_slug": body.avenue_slug, "action_class": action_class}


class LeadQualifyBody(BaseModel):
    intent: str = Field(
        ...,
        pattern=(
            "^(offer_request|pricing_question|objection|positive|"
            "not_interested|referral|unclear)$"
        ),
    )
    tier: str = Field(
        ...,
        pattern="^(hot|warm|cold|parked|disqualified)$",
    )
    reason_codes: list[str] = Field(default_factory=list)
    avenue_slug_override: Optional[str] = Field(None, max_length=60)
    notes: Optional[str] = Field(None, max_length=4000)


@router.post("/leads/{lead_id}/qualify")
async def gm_leads_qualify(
    lead_id: str,
    body: LeadQualifyBody,
    current_user: OperatorUser,
    db: DBSession,
):
    from apps.api.services.gm_front_of_funnel_service import qualify_lead

    lid = _parse_uuid(lead_id)
    action_class = classify_action(confidence=1.0, money_involved=True)
    forbid_escalation_as_mutation(
        tool_name="leads.qualify", action_class=action_class,
    )
    try:
        result = await qualify_lead(
            db,
            org_id=current_user.organization_id,
            lead_id=lid,
            intent=body.intent,
            tier=body.tier,
            reason_codes=body.reason_codes,
            avenue_slug_override=body.avenue_slug_override,
            notes=body.notes,
            actor_type="operator",
            actor_id=current_user.email or str(current_user.id),
        )
    except KeyError:
        raise HTTPException(404, "Lead not found")
    except PermissionError as pe:
        raise HTTPException(403, str(pe))
    except ValueError as ve:
        raise HTTPException(400, str(ve))

    await audit_gm_write(
        db, actor=current_user, tool_name="leads.qualify",
        entity_type="sponsor_target", entity_id=lid,
        decision="executed", action_class=action_class,
        details={
            "tier": body.tier,
            "intent": body.intent,
            "avenue_slug": result.get("avenue_slug"),
            "reason_codes": body.reason_codes,
        },
    )
    await db.commit()
    return {**result, "action_class": action_class}


class LeadRouteToProposalLineItem(BaseModel):
    description: str = Field(..., max_length=500)
    unit_amount_cents: int = Field(..., ge=0)
    quantity: int = Field(1, ge=1)
    currency: str = "usd"
    package_slug: Optional[str] = Field(None, max_length=100)
    position: int = 0


class LeadRouteToProposalBody(BaseModel):
    package_slug: Optional[str] = Field(None, max_length=100)
    title: Optional[str] = Field(None, max_length=500)
    summary: str = ""
    line_items: list[LeadRouteToProposalLineItem] = Field(..., min_length=1)
    notes: Optional[str] = None


@router.post("/leads/{lead_id}/route-to-proposal", status_code=201)
async def gm_leads_route_to_proposal(
    lead_id: str,
    body: LeadRouteToProposalBody,
    current_user: OperatorUser,
    db: DBSession,
):
    from apps.api.services.gm_front_of_funnel_service import route_lead_to_proposal

    lid = _parse_uuid(lead_id)
    action_class = classify_action(confidence=1.0, money_involved=True)
    forbid_escalation_as_mutation(
        tool_name="leads.route_to_proposal", action_class=action_class,
    )
    try:
        proposal = await route_lead_to_proposal(
            db,
            org_id=current_user.organization_id,
            lead_id=lid,
            package_slug=body.package_slug,
            line_items=[li.model_dump() for li in body.line_items],
            title=body.title,
            summary=body.summary,
            notes=body.notes,
            actor_id=current_user.email or str(current_user.id),
        )
    except KeyError:
        raise HTTPException(404, "Lead not found")
    except PermissionError as pe:
        raise HTTPException(403, str(pe))
    except ValueError as ve:
        raise HTTPException(400, str(ve))

    await audit_gm_write(
        db, actor=current_user, tool_name="leads.route_to_proposal",
        entity_type="proposal", entity_id=proposal.id,
        decision="executed", action_class=action_class,
        details={
            "lead_id": str(lid),
            "proposal_id": str(proposal.id),
            "avenue_slug": proposal.avenue_slug,
            "package_slug": body.package_slug,
            "total_amount_cents": proposal.total_amount_cents,
        },
    )
    await db.commit()
    return {
        "lead_id": str(lid),
        "proposal_id": str(proposal.id),
        "status": proposal.status,
        "total_amount_cents": proposal.total_amount_cents,
        "avenue_slug": proposal.avenue_slug,
        "action_class": action_class,
    }


class OutreachLaunchBody(BaseModel):
    avenue_slug: str = Field(..., min_length=1, max_length=60)
    lead_ids: Optional[list[uuid.UUID]] = None
    sequence_template_slug: str = Field("default_v1", max_length=100)
    max_leads: int = Field(200, ge=1, le=1000)


@router.post("/outreach/launch", status_code=201)
async def gm_outreach_launch(
    body: OutreachLaunchBody,
    current_user: OperatorUser,
    db: DBSession,
):
    from apps.api.services.gm_front_of_funnel_service import launch_outreach_for_segment

    action_class = classify_action(confidence=1.0, money_involved=True)
    forbid_escalation_as_mutation(
        tool_name="outreach.launch", action_class=action_class,
    )
    try:
        result = await launch_outreach_for_segment(
            db,
            org_id=current_user.organization_id,
            avenue_slug=body.avenue_slug,
            lead_ids=body.lead_ids,
            sequence_template_slug=body.sequence_template_slug,
            max_leads=body.max_leads,
            actor_id=current_user.email or str(current_user.id),
        )
    except ValueError as ve:
        raise HTTPException(400, str(ve))

    await audit_gm_write(
        db, actor=current_user, tool_name="outreach.launch",
        entity_type="brand", entity_id=None,
        decision="executed", action_class=action_class,
        details={
            "avenue_slug": body.avenue_slug,
            "scheduled": result["scheduled"],
            "skipped": result["skipped"],
            "sequence_template_slug": body.sequence_template_slug,
        },
    )
    await db.commit()
    return {**result, "action_class": action_class}


class OutreachPauseBody(BaseModel):
    avenue_slug: Optional[str] = Field(None, max_length=60)
    sequence_ids: Optional[list[uuid.UUID]] = None


@router.post("/outreach/pause")
async def gm_outreach_pause(
    body: OutreachPauseBody,
    current_user: OperatorUser,
    db: DBSession,
):
    from apps.api.services.gm_front_of_funnel_service import pause_outreach_for_avenue

    if not body.avenue_slug and not body.sequence_ids:
        raise HTTPException(
            400, "Must provide either avenue_slug or sequence_ids"
        )
    action_class = classify_action(confidence=1.0, money_involved=False)
    forbid_escalation_as_mutation(
        tool_name="outreach.pause", action_class=action_class,
    )
    result = await pause_outreach_for_avenue(
        db,
        org_id=current_user.organization_id,
        avenue_slug=body.avenue_slug,
        sequence_ids=body.sequence_ids,
        actor_id=current_user.email or str(current_user.id),
    )
    await audit_gm_write(
        db, actor=current_user, tool_name="outreach.pause",
        entity_type="brand", entity_id=None,
        decision="executed", action_class=action_class,
        details={"avenue_slug": body.avenue_slug, "paused": result["paused"]},
    )
    await db.commit()
    return {**result, "action_class": action_class}


class DraftRewriteBody(BaseModel):
    subject: Optional[str] = Field(None, max_length=1000)
    body_text: Optional[str] = Field(None, max_length=100_000)
    body_html: Optional[str] = Field(None, max_length=200_000)
    reason: Optional[str] = Field(None, max_length=2000)


@router.post("/replies/drafts/{draft_id}/rewrite")
async def gm_reply_draft_rewrite(
    draft_id: str,
    body: DraftRewriteBody,
    current_user: OperatorUser,
    db: DBSession,
):
    from apps.api.services.gm_front_of_funnel_service import rewrite_draft

    did = _parse_uuid(draft_id)
    draft = (
        await db.execute(select(EmailReplyDraft).where(EmailReplyDraft.id == did))
    ).scalar_one_or_none()
    if draft is None:
        raise HTTPException(404, "Draft not found")
    if draft.org_id != current_user.organization_id:
        raise HTTPException(403, "Draft belongs to another organization")
    if body.subject is None and body.body_text is None and body.body_html is None:
        raise HTTPException(
            400, "At least one of subject / body_text / body_html is required"
        )

    action_class = classify_action(confidence=1.0, money_involved=False)
    forbid_escalation_as_mutation(
        tool_name="replies.rewrite", action_class=action_class,
    )
    try:
        updated = await rewrite_draft(
            db, draft=draft,
            new_subject=body.subject,
            new_body_text=body.body_text,
            new_body_html=body.body_html,
            reason=body.reason,
            actor_id=current_user.email or str(current_user.id),
        )
    except ValueError as ve:
        raise HTTPException(400, str(ve))

    await audit_gm_write(
        db, actor=current_user, tool_name="replies.rewrite",
        entity_type="email_reply_draft", entity_id=draft.id,
        decision="executed", action_class=action_class,
        details={
            "version_count": len((updated.rewrite_history_json or {}).get("versions", [])),
            "reason": body.reason,
            "avenue_slug": draft.avenue_slug,
        },
    )
    await db.commit()
    return {
        "draft_id": str(draft.id),
        "status": draft.status,
        "avenue_slug": draft.avenue_slug,
        "version_count": len((updated.rewrite_history_json or {}).get("versions", [])),
        "action_class": action_class,
    }


@router.post("/replies/drafts/{draft_id}/send-now")
async def gm_reply_draft_send_now(
    draft_id: str,
    current_user: OperatorUser,
    db: DBSession,
):
    from apps.api.services.gm_front_of_funnel_service import force_send_draft

    did = _parse_uuid(draft_id)
    draft = (
        await db.execute(select(EmailReplyDraft).where(EmailReplyDraft.id == did))
    ).scalar_one_or_none()
    if draft is None:
        raise HTTPException(404, "Draft not found")
    if draft.org_id != current_user.organization_id:
        raise HTTPException(403, "Draft belongs to another organization")

    action_class = classify_action(confidence=1.0, money_involved=True)
    forbid_escalation_as_mutation(
        tool_name="replies.send_now", action_class=action_class,
    )
    try:
        result = await force_send_draft(
            db, draft=draft,
            actor_id=current_user.email or str(current_user.id),
        )
    except ValueError as ve:
        raise HTTPException(400, str(ve))

    await audit_gm_write(
        db, actor=current_user, tool_name="replies.send_now",
        entity_type="email_reply_draft", entity_id=draft.id,
        decision="executed" if draft.status == "sent" else "recorded",
        action_class=action_class,
        details={
            "status_after": draft.status,
            "sent_at": result.get("sent_at"),
            "avenue_slug": draft.avenue_slug,
            "batch_result": result.get("batch_result"),
        },
        severity="info" if draft.status == "sent" else "warning",
    )
    await db.commit()
    return {**result, "action_class": action_class}


# ═══════════════════════════════════════════════════════════════════════════
#  11. Batch 11 — retention / renewal / reactivation GM write authority
# ═══════════════════════════════════════════════════════════════════════════
#
# Four endpoints that close the ninth stage of the full-circle for
# every avenue: renew a recurring client, reactivate a lapsed one,
# upsell an expansion candidate, cancel a subscription. Each wraps
# one retention_service function; every call is audit-trailed and
# idempotent within its debounce window.


class RetentionLineItem(BaseModel):
    description: str = Field(..., max_length=500)
    unit_amount_cents: int = Field(..., ge=0)
    quantity: int = Field(1, ge=1)
    currency: str = "usd"
    package_slug: Optional[str] = Field(None, max_length=100)
    position: int = 0


class ClientRenewBody(BaseModel):
    package_slug: str = Field(..., min_length=1, max_length=100)
    line_items: list[RetentionLineItem] = Field(..., min_length=1)
    title: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None
    force: bool = False


@router.post("/clients/{client_id}/renew", status_code=201)
async def gm_client_renew(
    client_id: str,
    body: ClientRenewBody,
    current_user: OperatorUser,
    db: DBSession,
):
    """Trigger a renewal cycle for a recurring client. Creates a new
    Proposal linked back to the client's first proposal; idempotent
    within 24h (pass force=true to override).
    """
    from apps.api.services.retention_service import trigger_renewal

    cid = _parse_uuid(client_id)
    client = (
        await db.execute(select(Client).where(Client.id == cid))
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(404, "Client not found")
    if client.org_id != current_user.organization_id:
        raise HTTPException(403, "Client belongs to another organization")

    action_class = classify_action(confidence=1.0, money_involved=True)
    forbid_escalation_as_mutation(
        tool_name="clients.renew", action_class=action_class,
    )

    try:
        result = await trigger_renewal(
            db, client=client,
            package_slug=body.package_slug,
            line_items=[li.model_dump() for li in body.line_items],
            title=body.title, notes=body.notes,
            actor_type="operator",
            actor_id=current_user.email or str(current_user.id),
            force=body.force,
        )
    except ValueError as ve:
        raise HTTPException(400, str(ve))

    await audit_gm_write(
        db, actor=current_user, tool_name="clients.renew",
        entity_type="client", entity_id=client.id,
        decision="executed" if result.get("triggered") else "recorded",
        action_class=action_class,
        details={
            "package_slug": body.package_slug,
            "triggered": bool(result.get("triggered")),
            "reason": result.get("reason"),
            "proposal_id": result.get("proposal_id"),
            "retention_event_id": result.get("retention_event_id"),
            "avenue_slug": client.avenue_slug,
        },
        severity="info" if result.get("triggered") else "warning",
    )
    await db.commit()
    return {"client_id": str(client.id), **result, "action_class": action_class}


class ClientReactivateBody(BaseModel):
    template_slug: str = Field("reactivation_default_v1", max_length=100)
    subject: Optional[str] = Field(None, max_length=1000)
    body_override: Optional[str] = Field(None, max_length=50_000)
    notes: Optional[str] = None
    force: bool = False


@router.post("/clients/{client_id}/reactivate")
async def gm_client_reactivate(
    client_id: str,
    body: ClientReactivateBody,
    current_user: OperatorUser,
    db: DBSession,
):
    """Send a reactivation email to a lapsed client. Debounced 14d."""
    from apps.api.services.retention_service import trigger_reactivation

    cid = _parse_uuid(client_id)
    client = (
        await db.execute(select(Client).where(Client.id == cid))
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(404, "Client not found")
    if client.org_id != current_user.organization_id:
        raise HTTPException(403, "Client belongs to another organization")

    action_class = classify_action(confidence=1.0, money_involved=False)
    forbid_escalation_as_mutation(
        tool_name="clients.reactivate", action_class=action_class,
    )

    result = await trigger_reactivation(
        db, client=client,
        template_slug=body.template_slug,
        subject_override=body.subject,
        body_override=body.body_override,
        notes=body.notes,
        actor_type="operator",
        actor_id=current_user.email or str(current_user.id),
        force=body.force,
    )
    await audit_gm_write(
        db, actor=current_user, tool_name="clients.reactivate",
        entity_type="client", entity_id=client.id,
        decision="executed" if result.get("triggered") else "recorded",
        action_class=action_class,
        details={
            "template_slug": body.template_slug,
            "triggered": bool(result.get("triggered")),
            "sent": bool(result.get("sent")),
            "reason": result.get("reason"),
            "error": result.get("error"),
            "retention_event_id": result.get("retention_event_id"),
            "avenue_slug": client.avenue_slug,
        },
        severity="info" if result.get("sent") else "warning",
    )
    await db.commit()
    return {"client_id": str(client.id), **result, "action_class": action_class}


class ClientUpsellBody(BaseModel):
    package_slug: str = Field(..., min_length=1, max_length=100)
    line_items: list[RetentionLineItem] = Field(..., min_length=1)
    title: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None
    force: bool = False


@router.post("/clients/{client_id}/upsell", status_code=201)
async def gm_client_upsell(
    client_id: str,
    body: ClientUpsellBody,
    current_user: OperatorUser,
    db: DBSession,
):
    """Offer an upsell — creates a new Proposal keyed to the client's
    avenue with ``extra_json.retention_source='upsell'``. Debounced 7d.
    """
    from apps.api.services.retention_service import trigger_upsell

    cid = _parse_uuid(client_id)
    client = (
        await db.execute(select(Client).where(Client.id == cid))
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(404, "Client not found")
    if client.org_id != current_user.organization_id:
        raise HTTPException(403, "Client belongs to another organization")

    action_class = classify_action(confidence=1.0, money_involved=True)
    forbid_escalation_as_mutation(
        tool_name="clients.upsell", action_class=action_class,
    )
    try:
        result = await trigger_upsell(
            db, client=client,
            package_slug=body.package_slug,
            line_items=[li.model_dump() for li in body.line_items],
            title=body.title, notes=body.notes,
            actor_type="operator",
            actor_id=current_user.email or str(current_user.id),
            force=body.force,
        )
    except ValueError as ve:
        raise HTTPException(400, str(ve))

    await audit_gm_write(
        db, actor=current_user, tool_name="clients.upsell",
        entity_type="client", entity_id=client.id,
        decision="executed" if result.get("triggered") else "recorded",
        action_class=action_class,
        details={
            "package_slug": body.package_slug,
            "triggered": bool(result.get("triggered")),
            "reason": result.get("reason"),
            "proposal_id": result.get("proposal_id"),
            "retention_event_id": result.get("retention_event_id"),
            "avenue_slug": client.avenue_slug,
        },
        severity="info" if result.get("triggered") else "warning",
    )
    await db.commit()
    return {"client_id": str(client.id), **result, "action_class": action_class}


class ClientCancelBody(BaseModel):
    reason: str = Field(..., min_length=1, max_length=200)
    effective_at_iso: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=4000)


@router.post("/clients/{client_id}/cancel-subscription")
async def gm_client_cancel_subscription(
    client_id: str,
    body: ClientCancelBody,
    current_user: OperatorUser,
    db: DBSession,
):
    """Terminal cancellation — flips retention_state to 'churned' and
    is_recurring to False. Idempotent (returns the existing event
    if client is already churned)."""
    from datetime import datetime as _dt, timezone as _tz
    from apps.api.services.retention_service import cancel_subscription

    cid = _parse_uuid(client_id)
    client = (
        await db.execute(select(Client).where(Client.id == cid))
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(404, "Client not found")
    if client.org_id != current_user.organization_id:
        raise HTTPException(403, "Client belongs to another organization")

    action_class = classify_action(confidence=1.0, money_involved=True)
    forbid_escalation_as_mutation(
        tool_name="clients.cancel_subscription", action_class=action_class,
    )

    eff_at = None
    if body.effective_at_iso:
        try:
            eff_at = _dt.fromisoformat(
                body.effective_at_iso.replace("Z", "+00:00")
            )
            if eff_at.tzinfo is None:
                eff_at = eff_at.replace(tzinfo=_tz.utc)
        except ValueError:
            raise HTTPException(400, f"Invalid effective_at_iso: {body.effective_at_iso}")

    result = await cancel_subscription(
        db, client=client,
        reason=body.reason,
        effective_at=eff_at,
        notes=body.notes,
        actor_type="operator",
        actor_id=current_user.email or str(current_user.id),
    )
    await audit_gm_write(
        db, actor=current_user, tool_name="clients.cancel_subscription",
        entity_type="client", entity_id=client.id,
        decision="executed" if result.get("triggered") else "recorded",
        action_class=action_class,
        details={
            "reason": body.reason,
            "effective_at_iso": body.effective_at_iso,
            "triggered": bool(result.get("triggered")),
            "previous_state": result.get("previous_state"),
            "new_state": result.get("new_state"),
            "retention_event_id": result.get("retention_event_id"),
            "avenue_slug": client.avenue_slug,
        },
    )
    await db.commit()
    return {"client_id": str(client.id), **result, "action_class": action_class}


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
