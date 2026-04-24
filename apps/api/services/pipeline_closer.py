"""Pipeline Closer — handles the consequences of revenue events automatically.

When money arrives (webhook, manual entry, ledger write), this service:
1. Updates deal stage (prospect→won, negotiation→completed)
2. Creates success memory entries
3. Reinforces winning patterns
4. Generates post-close follow-up actions
5. Triggers next-best revenue actions
6. Updates the control layer

Money arriving should change the machine everywhere it should.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_action, emit_event
from packages.db.models.core import Brand
from packages.db.models.learning import MemoryEntry
from packages.db.models.offers import SponsorOpportunity
from packages.db.models.revenue_ledger import RevenueLedgerEntry
from packages.db.models.saas_metrics import HighTicketDeal

logger = structlog.get_logger()


async def handle_payment_received(
    db: AsyncSession,
    ledger_entry: RevenueLedgerEntry,
) -> dict:
    """Handle all downstream consequences of a payment arriving.

    This is called after a RevenueLedgerEntry is created from a webhook
    or manual entry. It closes the loop: payment → pipeline → memory → action.
    """
    brand_id = ledger_entry.brand_id
    org_id = (await db.execute(select(Brand.organization_id).where(Brand.id == brand_id))).scalar()
    source = ledger_entry.revenue_source_type
    amount = ledger_entry.gross_amount

    changes = []

    # ── 1. Update deal stage if applicable ──
    if source == "sponsor_payment" and ledger_entry.sponsor_id:
        deals = (
            (
                await db.execute(
                    select(SponsorOpportunity).where(
                        SponsorOpportunity.sponsor_id == ledger_entry.sponsor_id,
                        SponsorOpportunity.brand_id == brand_id,
                        SponsorOpportunity.status.notin_(["completed", "lost"]),
                    )
                )
            )
            .scalars()
            .all()
        )
        for deal in deals:
            old_status = deal.status
            deal.status = "completed"
            changes.append(f"sponsor deal '{deal.title}': {old_status} → completed")

    elif source in ("service_fee", "consulting_fee") and ledger_entry.source_object_id:
        htd = (
            await db.execute(select(HighTicketDeal).where(HighTicketDeal.id == ledger_entry.source_object_id))
        ).scalar_one_or_none()
        if htd and htd.stage not in ("closed_won", "closed_lost"):
            old_stage = htd.stage
            htd.stage = "closed_won"
            changes.append(f"deal '{htd.customer_name}': {old_stage} → closed_won")

    # ── 2. Create success memory entry ──
    memory = MemoryEntry(
        brand_id=brand_id,
        memory_type="revenue_success",
        key=f"ledger_{ledger_entry.id}",
        value=f"${amount:.2f} received from {source}"
        + (f" via {ledger_entry.payment_processor}" if ledger_entry.payment_processor else ""),
        confidence=0.95,
        source_type="pipeline_closer",
        source_content_id=ledger_entry.content_item_id,
        structured_value={
            "source_type": source,
            "amount": amount,
            "offer_id": str(ledger_entry.offer_id) if ledger_entry.offer_id else None,
            "content_id": str(ledger_entry.content_item_id) if ledger_entry.content_item_id else None,
            "processor": ledger_entry.payment_processor,
        },
    )
    db.add(memory)
    changes.append("success memory entry created")

    # ── 3. Create post-close actions ──
    if amount > 0:  # ANY payment triggers expansion — no fixed threshold
        # High-value payment → create expansion action
        await emit_action(
            db,
            org_id=org_id,
            action_type="create_content_for_offer",
            title=f"Post-close: create more content for ${amount:.0f} revenue path ({source})",
            description=f"This {source} generated ${amount:.2f}. Create more content/offers in this path.",
            category="opportunity",
            priority="high",
            brand_id=brand_id,
            source_module="pipeline_closer",
            entity_type="revenue_ledger",
            entity_id=ledger_entry.id,
            action_payload={"autonomy_level": "assisted", "confidence": 0.8},
        )
        changes.append("post-close expansion action created")

    if source == "sponsor_payment":
        # After sponsor payment, queue repeat deal outreach
        await emit_action(
            db,
            org_id=org_id,
            action_type="escalate_sponsor_opportunity",
            title=f"Re-engage: propose follow-up deal after ${amount:.0f} sponsor success",
            description="Previous sponsor deal completed successfully. Propose a renewal or expanded partnership.",
            category="monetization",
            priority="medium",
            brand_id=brand_id,
            source_module="pipeline_closer",
            action_payload={"autonomy_level": "assisted", "confidence": 0.7},
        )
        changes.append("sponsor re-engagement action created")

    # ── 4. Emit learning event ──
    await emit_event(
        db,
        domain="monetization",
        event_type="pipeline.payment_handled",
        summary=f"Payment handled: ${amount:.2f} from {source} → {len(changes)} downstream changes",
        org_id=org_id,
        brand_id=brand_id,
        entity_type="revenue_ledger",
        entity_id=ledger_entry.id,
        details={"amount": amount, "source": source, "changes": changes},
    )

    await db.flush()
    return {"changes": changes, "changes_count": len(changes)}


async def auto_create_brief_from_decision(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    decision_class: str,
    objective: str,
    target_platform: str | None = None,
) -> dict:
    """Auto-generate a content brief from a brain decision or revenue opportunity.

    When the machine decides "create content for monetize opportunity X,"
    this function actually creates the ContentBrief instead of just labeling it.
    """
    from packages.db.enums import ContentType
    from packages.db.models.content import ContentBrief
    from packages.db.models.offers import Offer

    # Find the best offer to monetize with
    best_offer = (
        await db.execute(
            select(Offer)
            .where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
            .order_by(Offer.epc.desc().nullslast())
            .limit(1)
        )
    ).scalar_one_or_none()

    # Determine content type based on platform
    content_type = ContentType.SHORT_VIDEO
    if target_platform in ("youtube", "blog"):
        content_type = ContentType.LONG_VIDEO
    elif target_platform in ("instagram", "pinterest"):
        content_type = ContentType.STATIC_IMAGE

    brief = ContentBrief(
        brand_id=brand_id,
        title=f"[Auto] {objective[:200]}",
        content_type=content_type,
        target_platform=target_platform or "youtube",
        hook=f"Auto-generated brief from {decision_class} decision",
        angle=objective[:300],
        offer_id=best_offer.id if best_offer else None,
        cta_strategy=f"Promote {best_offer.name}" if best_offer else "Build audience",
        status="draft",
    )
    db.add(brief)
    await db.flush()

    org_id = (await db.execute(select(Brand.organization_id).where(Brand.id == brand_id))).scalar()
    await emit_event(
        db,
        domain="content",
        event_type="brief.auto_created",
        summary=f"Auto-brief: {brief.title[:60]}",
        org_id=org_id,
        brand_id=brand_id,
        entity_type="content_brief",
        entity_id=brief.id,
        details={"decision_class": decision_class, "offer_id": str(best_offer.id) if best_offer else None},
    )

    return {
        "brief_id": str(brief.id),
        "title": brief.title,
        "content_type": content_type.value,
        "platform": brief.target_platform,
        "offer_linked": best_offer.name if best_offer else None,
        "status": "draft_created",
    }
