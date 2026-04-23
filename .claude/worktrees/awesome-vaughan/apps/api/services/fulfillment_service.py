"""Fulfillment service — bridges payment to delivery.

When a Stripe payment succeeds, this service:
1. Creates a FulfillmentOrder record (idempotent via ledger_entry_id unique constraint)
2. Sends an onboarding email via EmailSendRequest
3. Seeds content briefs for the purchased package
4. Updates fulfillment status and emits events

The onboarding email is picked up by the existing execute_emails beat task.
The content briefs are picked up by the existing process_pending_briefs beat task.
No new workers or beat entries needed.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


async def initiate_fulfillment(
    db: AsyncSession,
    ledger_entry,  # RevenueLedgerEntry
    customer_email: str,
    customer_name: str = "",
) -> dict[str, Any]:
    """Create fulfillment order and trigger onboarding + content seeding.

    Idempotent: if a FulfillmentOrder already exists for this ledger entry, returns early.
    """
    from packages.db.models.fulfillment import FulfillmentOrder
    from packages.db.models.live_execution import EmailSendRequest
    from packages.db.models.content import ContentBrief, ContentType
    from packages.db.models.offers import Offer
    from packages.db.models.core import Brand
    from apps.api.services.event_bus import emit_event

    # ── Idempotency check ──
    existing = (await db.execute(
        select(FulfillmentOrder).where(
            FulfillmentOrder.ledger_entry_id == ledger_entry.id,
        )
    )).scalar_one_or_none()

    if existing:
        logger.info("fulfillment.already_exists", order_id=str(existing.id))
        return {"success": True, "status": "already_fulfilled", "order_id": str(existing.id)}

    # ── Determine fulfillment type ──
    source_type = ledger_entry.revenue_source_type or "service_fee"
    type_map = {
        "service_fee": "onboarding",
        "consulting_fee": "consulting_kickoff",
        "product_sale": "digital_delivery",
        "digital_product": "digital_delivery",
        "membership_payment": "onboarding",
    }
    fulfillment_type = type_map.get(source_type, "onboarding")

    # ── Create FulfillmentOrder ──
    order = FulfillmentOrder(
        brand_id=ledger_entry.brand_id,
        ledger_entry_id=ledger_entry.id,
        offer_id=ledger_entry.offer_id,
        customer_email=customer_email,
        customer_name=customer_name,
        fulfillment_type=fulfillment_type,
        status="pending",
        gross_amount=ledger_entry.gross_amount or 0.0,
        steps_completed={},
        metadata_json={
            "payment_processor": ledger_entry.payment_processor,
            "external_transaction_id": ledger_entry.external_transaction_id,
        },
    )
    db.add(order)
    await db.flush()

    steps = {}

    # ── Step 1: Onboarding email ──
    if customer_email:
        first_name = customer_name.split()[0] if customer_name else "there"
        amount = ledger_entry.gross_amount or 0

        db.add(EmailSendRequest(
            brand_id=ledger_entry.brand_id,
            to_email=customer_email,
            subject=f"Welcome! Your purchase is confirmed",
            body_html=_onboarding_html(first_name, amount),
            body_text=_onboarding_text(first_name, amount),
            status="queued",
            provider="smtp",
            sequence_step="onboarding",
            metadata_json={
                "fulfillment_order_id": str(order.id),
                "source": "fulfillment_service",
            },
        ))
        steps["onboarding_email"] = datetime.now(timezone.utc).isoformat()
        order.status = "email_sent"

    # ── Step 2: Seed content briefs for purchased package ──
    briefs_created = 0
    if ledger_entry.offer_id:
        try:
            offer = (await db.execute(
                select(Offer).where(Offer.id == ledger_entry.offer_id)
            )).scalar_one_or_none()

            if offer:
                for platform in ["tiktok", "instagram"]:
                    brief = ContentBrief(
                        brand_id=ledger_entry.brand_id,
                        offer_id=offer.id,
                        title=f"[Fulfillment] {offer.name} — {platform.title()} content",
                        content_type=ContentType.SHORT_VIDEO,
                        target_platform=platform,
                        hook=f"Opening hook for {offer.name}",
                        angle=f"Deliver on {offer.name} — client-facing content",
                        key_points=[
                            f"Deliver on {offer.name} promise",
                            "Show tangible results",
                            "Professional quality",
                        ],
                        cta_strategy="Client-appropriate CTA",
                        monetization_integration=offer.monetization_method or "lead_gen",
                        status="draft",
                        brief_metadata={
                            "source": "fulfillment_service",
                            "fulfillment_order_id": str(order.id),
                            "qa_retry_count": 0,
                        },
                    )
                    db.add(brief)
                    briefs_created += 1

                steps["briefs_created"] = briefs_created
                order.status = "briefs_created"
        except Exception as exc:
            logger.warning("fulfillment.brief_seeding_failed", error=str(exc))

    # ── Finalize ──
    order.steps_completed = steps
    if order.status != "pending":
        order.status = "completed"
    await db.flush()

    # ── Emit event ──
    brand = (await db.execute(
        select(Brand).where(Brand.id == ledger_entry.brand_id)
    )).scalar_one_or_none()

    org_id = brand.organization_id if brand else None

    try:
        await emit_event(
            db, domain="monetization", event_type="fulfillment.initiated",
            summary=f"Fulfillment started for ${ledger_entry.gross_amount:.2f} payment — "
                    f"email {'sent' if customer_email else 'skipped'}, {briefs_created} briefs seeded",
            org_id=org_id,
            brand_id=ledger_entry.brand_id,
            entity_type="fulfillment_order", entity_id=order.id,
            details={
                "customer_email": customer_email,
                "amount": ledger_entry.gross_amount,
                "fulfillment_type": fulfillment_type,
                "briefs_created": briefs_created,
                "steps": steps,
            },
        )
    except Exception:
        pass

    logger.info(
        "fulfillment.completed",
        order_id=str(order.id),
        customer_email=customer_email,
        briefs=briefs_created,
    )

    return {
        "success": True,
        "order_id": str(order.id),
        "status": order.status,
        "steps": steps,
        "briefs_created": briefs_created,
    }


# ---------------------------------------------------------------------------
# Email templates
# ---------------------------------------------------------------------------

def _onboarding_html(name: str, amount: float) -> str:
    return f"""<p>Hey {name},</p>
<p>Your payment of ${amount:.2f} has been confirmed. Welcome aboard!</p>
<p>Here's what happens next:</p>
<ul>
<li>Our team is already setting up your content pipeline</li>
<li>You'll receive your first content drafts within 48 hours</li>
<li>We'll reach out to schedule your strategy kickoff call</li>
</ul>
<p>If you have any questions in the meantime, just reply to this email.</p>
<p>Looking forward to working together!</p>"""


def _onboarding_text(name: str, amount: float) -> str:
    return (
        f"Hey {name},\n\n"
        f"Your payment of ${amount:.2f} has been confirmed. Welcome aboard!\n\n"
        f"Here's what happens next:\n"
        f"- Our team is already setting up your content pipeline\n"
        f"- You'll receive your first content drafts within 48 hours\n"
        f"- We'll reach out to schedule your strategy kickoff call\n\n"
        f"If you have any questions in the meantime, just reply to this email.\n\n"
        f"Looking forward to working together!"
    )
