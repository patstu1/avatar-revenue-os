"""Proposals router — conversion-backbone CRUD.

Thin HTTP layer over ``apps.api.services.proposals_service``. Every
state-changing endpoint requires ``OperatorUser`` auth and is org-scoped
against ``current_user.organization_id`` — cross-org access is refused
with HTTP 403.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from apps.api.deps import DBSession, OperatorUser
from apps.api.services.proposals_service import (
    LineItemInput,
)
from apps.api.services.proposals_service import (
    create_proposal as svc_create_proposal,
)
from apps.api.services.proposals_service import (
    mark_proposal_sent as svc_mark_sent,
)
from apps.api.services.proposals_service import (
    record_payment_link as svc_record_payment_link,
)
from packages.db.models.proposals import (
    Payment,
    PaymentLink,
    Proposal,
    ProposalLineItem,
)

router = APIRouter(prefix="/proposals", tags=["Proposals"])
logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════════════
#  Pydantic bodies
# ═══════════════════════════════════════════════════════════════════════════


class LineItemBody(BaseModel):
    description: str = Field(..., max_length=500)
    unit_amount_cents: int = Field(..., ge=0)
    quantity: int = Field(1, ge=1)
    offer_id: uuid.UUID | None = None
    package_slug: str | None = Field(None, max_length=100)
    currency: str = Field("usd", max_length=10)
    position: int = 0


class CreateProposalBody(BaseModel):
    recipient_email: str = Field(..., max_length=255)
    title: str = Field(..., max_length=500)
    line_items: list[LineItemBody] = Field(..., min_length=1)
    brand_id: uuid.UUID | None = None
    thread_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    draft_id: uuid.UUID | None = None
    operator_action_id: uuid.UUID | None = None
    recipient_name: str = ""
    recipient_company: str = ""
    summary: str = ""
    package_slug: str | None = None
    currency: str = "usd"
    notes: str | None = None


class CreatePaymentLinkBody(BaseModel):
    """Create a Stripe payment link for an existing proposal.

    ``amount_cents`` defaults to the proposal's ``total_amount_cents``
    when omitted, so the typical flow is POST with an empty body.
    """

    amount_cents: int | None = Field(None, ge=0)
    currency: str | None = Field(None, max_length=10)
    product_name: str | None = Field(None, max_length=500)


# ═══════════════════════════════════════════════════════════════════════════
#  Create / list / fetch
# ═══════════════════════════════════════════════════════════════════════════


@router.post("", status_code=201)
async def create_proposal(
    body: CreateProposalBody,
    current_user: OperatorUser,
    db: DBSession,
):
    proposal = await svc_create_proposal(
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
        thread_id=body.thread_id,
        message_id=body.message_id,
        draft_id=body.draft_id,
        operator_action_id=body.operator_action_id,
        recipient_name=body.recipient_name,
        recipient_company=body.recipient_company,
        summary=body.summary,
        package_slug=body.package_slug,
        currency=body.currency,
        created_by_actor_type="operator",
        created_by_actor_id=str(current_user.id),
        notes=body.notes,
    )
    await db.commit()
    return _proposal_response(proposal, [], [], [])


@router.get("")
async def list_proposals(
    current_user: OperatorUser,
    db: DBSession,
    status: str | None = None,
    limit: int = 50,
):
    q = select(Proposal).where(
        Proposal.org_id == current_user.organization_id,
        Proposal.is_active.is_(True),
    )
    if status:
        q = q.where(Proposal.status == status)
    q = q.order_by(desc(Proposal.created_at)).limit(max(1, min(200, limit)))
    rows = (await db.execute(q)).scalars().all()

    return [_proposal_summary(p) for p in rows]


@router.get("/{proposal_id}")
async def get_proposal(
    proposal_id: str,
    current_user: OperatorUser,
    db: DBSession,
):
    pid = _parse_uuid(proposal_id)
    proposal = await _require_owned_proposal(db, pid, current_user.organization_id)

    line_items = (
        (
            await db.execute(
                select(ProposalLineItem)
                .where(ProposalLineItem.proposal_id == proposal.id)
                .order_by(ProposalLineItem.position, ProposalLineItem.created_at)
            )
        )
        .scalars()
        .all()
    )

    links = (
        (
            await db.execute(
                select(PaymentLink).where(PaymentLink.proposal_id == proposal.id).order_by(desc(PaymentLink.created_at))
            )
        )
        .scalars()
        .all()
    )

    payments = (
        (await db.execute(select(Payment).where(Payment.proposal_id == proposal.id).order_by(desc(Payment.created_at))))
        .scalars()
        .all()
    )

    return _proposal_response(proposal, line_items, links, payments)


# ═══════════════════════════════════════════════════════════════════════════
#  Add line item
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/{proposal_id}/line-items", status_code=201)
async def add_line_item(
    proposal_id: str,
    body: LineItemBody,
    current_user: OperatorUser,
    db: DBSession,
):
    pid = _parse_uuid(proposal_id)
    proposal = await _require_owned_proposal(db, pid, current_user.organization_id)
    if proposal.status not in ("draft",):
        raise HTTPException(400, f"Cannot add line items to a proposal in status={proposal.status}")

    item = ProposalLineItem(
        proposal_id=proposal.id,
        offer_id=body.offer_id,
        package_slug=body.package_slug,
        description=body.description[:500],
        quantity=body.quantity,
        unit_amount_cents=body.unit_amount_cents,
        total_amount_cents=body.quantity * body.unit_amount_cents,
        currency=body.currency,
        position=body.position,
    )
    db.add(item)
    proposal.total_amount_cents = (proposal.total_amount_cents or 0) + item.total_amount_cents
    await db.commit()

    return {
        "id": str(item.id),
        "proposal_id": str(item.proposal_id),
        "description": item.description,
        "quantity": item.quantity,
        "unit_amount_cents": item.unit_amount_cents,
        "total_amount_cents": item.total_amount_cents,
        "currency": item.currency,
        "position": item.position,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Create payment link
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/{proposal_id}/payment-link", status_code=201)
async def create_payment_link_for_proposal(
    proposal_id: str,
    body: CreatePaymentLinkBody,
    current_user: OperatorUser,
    db: DBSession,
):
    """Create a Stripe Payment Link and persist it against the proposal.

    Reuses ``stripe_billing_service.create_payment_link`` so Stripe
    infrastructure is not rebuilt. Metadata includes ``proposal_id`` so
    the incoming Stripe webhook can resolve the owning proposal.
    """
    from apps.api.services.stripe_billing_service import create_payment_link

    pid = _parse_uuid(proposal_id)
    proposal = await _require_owned_proposal(db, pid, current_user.organization_id)

    amount_cents = body.amount_cents or proposal.total_amount_cents
    if amount_cents <= 0:
        raise HTTPException(400, "Proposal has no total_amount_cents and no amount override")

    currency = body.currency or proposal.currency or "usd"
    product_name = body.product_name or proposal.title

    stripe_result = await create_payment_link(
        amount_cents=amount_cents,
        currency=currency,
        product_name=product_name,
        metadata={
            "org_id": str(current_user.organization_id),
            "proposal_id": str(proposal.id),
            "brand_id": str(proposal.brand_id) if proposal.brand_id else "",
            "source": "proposal",
        },
        db=db,
        org_id=current_user.organization_id,
    )
    if stripe_result.get("error") or not stripe_result.get("url"):
        raise HTTPException(
            502,
            f"Stripe payment link creation failed: {stripe_result.get('error') or 'no url returned'}",
        )

    link = await svc_record_payment_link(
        db,
        org_id=current_user.organization_id,
        url=stripe_result["url"],
        amount_cents=amount_cents,
        proposal_id=proposal.id,
        brand_id=proposal.brand_id,
        provider="stripe",
        provider_link_id=stripe_result.get("id"),
        currency=currency,
        source="proposal",
        metadata={"product_name": product_name},
    )
    await db.commit()

    return {
        "id": str(link.id),
        "proposal_id": str(proposal.id),
        "url": link.url,
        "status": link.status,
        "amount_cents": link.amount_cents,
        "currency": link.currency,
        "provider": link.provider,
        "provider_link_id": link.provider_link_id,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Mark sent
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/{proposal_id}/send")
async def send_proposal(
    proposal_id: str,
    current_user: OperatorUser,
    db: DBSession,
):
    """Transition a proposal to ``status='sent'``.

    This endpoint only records the state change + emits the
    ``proposal.sent`` event. Actual outbound email is the responsibility
    of ``proposal_drain`` or ``reply_engine.send_approved_drafts`` which
    call ``mark_proposal_sent`` directly.
    """
    pid = _parse_uuid(proposal_id)
    proposal = await _require_owned_proposal(db, pid, current_user.organization_id)

    try:
        proposal = await svc_mark_sent(
            db,
            proposal_id=proposal.id,
            actor_type="operator",
            actor_id=str(current_user.id),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    await db.commit()
    return {
        "id": str(proposal.id),
        "status": proposal.status,
        "sent_at": proposal.sent_at.isoformat() if proposal.sent_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Response serialisers + helpers
# ═══════════════════════════════════════════════════════════════════════════


def _proposal_summary(p: Proposal) -> dict:
    return {
        "id": str(p.id),
        "status": p.status,
        "recipient_email": p.recipient_email,
        "title": p.title,
        "total_amount_cents": p.total_amount_cents,
        "currency": p.currency,
        "package_slug": p.package_slug,
        "sent_at": p.sent_at.isoformat() if p.sent_at else None,
        "paid_at": p.paid_at.isoformat() if p.paid_at else None,
        "created_at": p.created_at.isoformat(),
    }


def _proposal_response(
    p: Proposal,
    line_items,
    links,
    payments,
) -> dict:
    return {
        **_proposal_summary(p),
        "brand_id": str(p.brand_id) if p.brand_id else None,
        "thread_id": str(p.thread_id) if p.thread_id else None,
        "draft_id": str(p.draft_id) if p.draft_id else None,
        "summary": p.summary,
        "recipient_name": p.recipient_name,
        "recipient_company": p.recipient_company,
        "line_items": [
            {
                "id": str(li.id),
                "description": li.description,
                "quantity": li.quantity,
                "unit_amount_cents": li.unit_amount_cents,
                "total_amount_cents": li.total_amount_cents,
                "currency": li.currency,
                "offer_id": str(li.offer_id) if li.offer_id else None,
                "package_slug": li.package_slug,
                "position": li.position,
            }
            for li in line_items
        ],
        "payment_links": [
            {
                "id": str(link.id),
                "url": link.url,
                "status": link.status,
                "amount_cents": link.amount_cents,
                "currency": link.currency,
                "provider": link.provider,
                "provider_link_id": link.provider_link_id,
                "completed_at": link.completed_at.isoformat() if link.completed_at else None,
            }
            for link in links
        ],
        "payments": [
            {
                "id": str(pay.id),
                "status": pay.status,
                "amount_cents": pay.amount_cents,
                "currency": pay.currency,
                "provider": pay.provider,
                "provider_event_id": pay.provider_event_id,
                "completed_at": pay.completed_at.isoformat() if pay.completed_at else None,
            }
            for pay in payments
        ],
    }


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid proposal id")


async def _require_owned_proposal(db, proposal_id: uuid.UUID, org_id: uuid.UUID) -> Proposal:
    proposal = (
        await db.execute(
            select(Proposal).where(
                Proposal.id == proposal_id,
                Proposal.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if proposal is None:
        raise HTTPException(404, "Proposal not found")
    if proposal.org_id != org_id:
        raise HTTPException(403, "Proposal belongs to another organization")
    return proposal
