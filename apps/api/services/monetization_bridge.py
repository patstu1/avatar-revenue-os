"""Monetization Bridge — connects the monetization layer to the operating system.

This service integrates monetization with the rest of the machine by:

1. Linking offers to content items (which content promotes which offer)
2. Tracking revenue events back to offers and content via attribution
3. Computing per-brand revenue state for the control layer
4. Surfacing monetization actions (opportunities, blockers, anomalies)
5. Emitting system events for monetization state changes

The existing monetization services handle business logic; this bridge
adds the horizontal integration that makes monetization operational.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_action, emit_event
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.creator_revenue import CreatorRevenueBlocker, CreatorRevenueEvent, CreatorRevenueOpportunity
from packages.db.models.monetization import CreditLedger, PackPurchase, PlanSubscription
from packages.db.models.offers import Offer
from packages.db.models.publishing import AttributionEvent, PerformanceMetric, PublishJob

logger = structlog.get_logger()


# ── Offer ↔ Content Linkage ──────────────────────────────────────────

async def assign_offer_to_content(
    db: AsyncSession,
    content_id: uuid.UUID,
    offer_id: uuid.UUID,
    *,
    org_id: Optional[uuid.UUID] = None,
    actor_id: Optional[str] = None,
) -> ContentItem:
    """Link an offer to a content item.

    The ContentItem model already has an offer_id FK — this function
    sets it and emits the appropriate events.
    """
    item = (await db.execute(
        select(ContentItem).where(ContentItem.id == content_id)
    )).scalar_one_or_none()
    if not item:
        raise ValueError(f"ContentItem {content_id} not found")

    offer = (await db.execute(
        select(Offer).where(Offer.id == offer_id)
    )).scalar_one_or_none()
    if not offer:
        raise ValueError(f"Offer {offer_id} not found")

    previous_offer = str(item.offer_id) if item.offer_id else None
    item.offer_id = offer_id
    item.monetization_method = offer.monetization_method if hasattr(offer, 'monetization_method') else None

    if not org_id:
        brand = (await db.execute(select(Brand.organization_id).where(Brand.id == item.brand_id))).scalar()
        org_id = brand

    await emit_event(
        db, domain="monetization", event_type="offer.assigned_to_content",
        summary=f"Offer '{offer.name[:40]}' assigned to content '{item.title[:40]}'",
        org_id=org_id, brand_id=item.brand_id,
        entity_type="content_item", entity_id=content_id,
        previous_state=previous_offer,
        new_state=str(offer_id),
        actor_type="human" if actor_id else "system",
        actor_id=actor_id,
        details={
            "offer_id": str(offer_id),
            "offer_name": offer.name,
            "payout_amount": float(offer.payout_amount) if offer.payout_amount else None,
            "epc": float(offer.epc) if offer.epc else None,
        },
    )

    await db.flush()
    return item


async def get_content_with_offers(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[dict]:
    """Get content items with their assigned offers for revenue tracking."""
    q = await db.execute(
        select(ContentItem, Offer)
        .outerjoin(Offer, ContentItem.offer_id == Offer.id)
        .where(ContentItem.brand_id == brand_id)
        .order_by(ContentItem.created_at.desc())
        .limit(limit)
    )
    results = q.all()
    return [
        {
            "content_id": str(row[0].id),
            "title": row[0].title,
            "status": row[0].status,
            "platform": row[0].platform,
            "content_type": row[0].content_type.value if hasattr(row[0].content_type, 'value') else str(row[0].content_type),
            "offer": {
                "id": str(row[1].id),
                "name": row[1].name,
                "payout_amount": float(row[1].payout_amount) if row[1].payout_amount else None,
                "epc": float(row[1].epc) if row[1].epc else None,
                "monetization_method": row[1].monetization_method if hasattr(row[1], 'monetization_method') else None,
            } if row[1] else None,
            "monetization_density_score": row[0].monetization_density_score,
        }
        for row in results
    ]


# ── Revenue State Per Brand ──────────────────────────────────────────

async def get_brand_revenue_state(
    db: AsyncSession,
    brand_id: uuid.UUID,
) -> dict:
    """Compute real-time revenue state for a brand.

    Aggregates from multiple sources:
    - PerformanceMetric (platform-reported revenue)
    - AttributionEvent (conversion events)
    - CreatorRevenueEvent (webhook-driven events)
    - Offer performance (epc * clicks)
    """
    now = datetime.now(timezone.utc)
    day_30 = now - timedelta(days=30)
    day_7 = now - timedelta(days=7)

    # Performance metrics revenue (platform-reported)
    perf_revenue_30d = (await db.execute(
        select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0)).where(
            PerformanceMetric.brand_id == brand_id,
            PerformanceMetric.created_at >= day_30,
        )
    )).scalar() or 0.0

    perf_revenue_7d = (await db.execute(
        select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0)).where(
            PerformanceMetric.brand_id == brand_id,
            PerformanceMetric.created_at >= day_7,
        )
    )).scalar() or 0.0

    # Attribution events (conversion value)
    attr_revenue_30d = (await db.execute(
        select(func.coalesce(func.sum(AttributionEvent.event_value), 0.0)).where(
            AttributionEvent.brand_id == brand_id,
            AttributionEvent.event_type == "conversion",
            AttributionEvent.created_at >= day_30,
        )
    )).scalar() or 0.0

    # Creator revenue events (webhook-driven)
    creator_revenue_30d = (await db.execute(
        select(func.coalesce(func.sum(CreatorRevenueEvent.revenue), 0.0)).where(
            CreatorRevenueEvent.brand_id == brand_id,
            CreatorRevenueEvent.created_at >= day_30,
        )
    )).scalar() or 0.0

    # Total impressions
    impressions_30d = (await db.execute(
        select(func.coalesce(func.sum(PerformanceMetric.impressions), 0)).where(
            PerformanceMetric.brand_id == brand_id,
            PerformanceMetric.created_at >= day_30,
        )
    )).scalar() or 0

    # Content with offers (monetized vs not)
    total_content = (await db.execute(
        select(func.count()).select_from(ContentItem).where(ContentItem.brand_id == brand_id)
    )).scalar() or 0

    monetized_content = (await db.execute(
        select(func.count()).select_from(ContentItem).where(
            ContentItem.brand_id == brand_id,
            ContentItem.offer_id.isnot(None),
        )
    )).scalar() or 0

    # Active offers
    active_offers = (await db.execute(
        select(func.count()).select_from(Offer).where(
            Offer.brand_id == brand_id,
            Offer.is_active.is_(True),
        )
    )).scalar() or 0

    # Revenue opportunities
    opportunities = (await db.execute(
        select(func.count()).select_from(CreatorRevenueOpportunity).where(
            CreatorRevenueOpportunity.brand_id == brand_id,
        )
    )).scalar() or 0

    # Revenue blockers
    blockers = (await db.execute(
        select(func.count()).select_from(CreatorRevenueBlocker).where(
            CreatorRevenueBlocker.brand_id == brand_id,
        )
    )).scalar() or 0

    # Conversion count
    conversions_30d = (await db.execute(
        select(func.count()).select_from(AttributionEvent).where(
            AttributionEvent.brand_id == brand_id,
            AttributionEvent.event_type == "conversion",
            AttributionEvent.created_at >= day_30,
        )
    )).scalar() or 0

    total_revenue = float(perf_revenue_30d) + float(attr_revenue_30d) + float(creator_revenue_30d)
    monetization_rate = (monetized_content / total_content * 100) if total_content > 0 else 0

    return {
        "brand_id": str(brand_id),
        "total_revenue_30d": total_revenue,
        "platform_revenue_30d": float(perf_revenue_30d),
        "attribution_revenue_30d": float(attr_revenue_30d),
        "creator_revenue_30d": float(creator_revenue_30d),
        "revenue_7d": float(perf_revenue_7d),
        "impressions_30d": impressions_30d,
        "conversions_30d": conversions_30d,
        "active_offers": active_offers,
        "total_content": total_content,
        "monetized_content": monetized_content,
        "monetization_rate": round(monetization_rate, 1),
        "revenue_opportunities": opportunities,
        "revenue_blockers": blockers,
    }


# ── Surface Monetization Actions ──────────────────────────────────────

async def surface_monetization_actions(
    db: AsyncSession,
    org_id: uuid.UUID,
    brand_id: uuid.UUID,
) -> list[dict]:
    """Scan monetization state and create operator actions.

    Translates revenue gaps, unmonetized content, offer opportunities,
    and blockers into actionable items in the control layer.
    """
    actions_created = []

    # 1. Unmonetized published content → "Assign offer" action
    unmonetized = await db.execute(
        select(ContentItem).where(
            ContentItem.brand_id == brand_id,
            ContentItem.status == "published",
            ContentItem.offer_id.is_(None),
        ).limit(5)
    )
    for item in unmonetized.scalars().all():
        action = await emit_action(
            db, org_id=org_id,
            action_type="assign_offer",
            title=f"Monetize: {item.title[:50]}",
            description="Published content with no offer assigned. Assign an offer to start earning.",
            category="monetization",
            priority="medium",
            brand_id=brand_id,
            entity_type="content_item",
            entity_id=item.id,
            source_module="monetization_bridge",
        )
        actions_created.append({"type": "assign_offer", "action_id": str(action.id)})

    # 2. Revenue blockers → "Address blocker" action
    blockers = await db.execute(
        select(CreatorRevenueBlocker).where(
            CreatorRevenueBlocker.brand_id == brand_id,
            CreatorRevenueBlocker.operator_action_needed.is_(True),
        ).limit(5)
    )
    for b in blockers.scalars().all():
        action = await emit_action(
            db, org_id=org_id,
            action_type="resolve_revenue_blocker",
            title=f"Revenue blocker: {b.blocker_type[:50] if b.blocker_type else 'unknown'}",
            description=f"Severity: {b.severity or 'unknown'}. Avenue: {b.avenue_type or 'N/A'}.",
            category="monetization",
            priority="high" if b.severity == "critical" else "medium",
            brand_id=brand_id,
            entity_type="revenue_blocker",
            entity_id=b.id,
            source_module="creator_revenue",
        )
        actions_created.append({"type": "revenue_blocker", "action_id": str(action.id)})

    # 3. High-value opportunities → "Pursue opportunity" action
    opportunities = await db.execute(
        select(CreatorRevenueOpportunity).where(
            CreatorRevenueOpportunity.brand_id == brand_id,
        ).order_by(CreatorRevenueOpportunity.expected_value.desc().nullslast()).limit(3)
    )
    for opp in opportunities.scalars().all():
        if opp.expected_value and opp.expected_value > 50:
            action = await emit_action(
                db, org_id=org_id,
                action_type="pursue_revenue_opportunity",
                title=f"Revenue opportunity: {opp.avenue_type or 'unknown'} (${opp.expected_value:.0f})",
                description=f"Priority: {opp.priority_score or 0:.0f}/100. Confidence: {opp.confidence or 0:.0%}.",
                category="monetization",
                priority="high" if opp.expected_value > 200 else "medium",
                brand_id=brand_id,
                entity_type="revenue_opportunity",
                entity_id=opp.id,
                source_module="creator_revenue",
            )
            actions_created.append({"type": "revenue_opportunity", "action_id": str(action.id)})

    # 4. Offers with no content → "Create content for offer" action
    orphan_offers = await db.execute(
        select(Offer).where(
            Offer.brand_id == brand_id,
            Offer.is_active.is_(True),
        ).limit(20)
    )
    for offer in orphan_offers.scalars().all():
        content_count = (await db.execute(
            select(func.count()).select_from(ContentItem).where(
                ContentItem.brand_id == brand_id,
                ContentItem.offer_id == offer.id,
            )
        )).scalar() or 0

        if content_count == 0:
            action = await emit_action(
                db, org_id=org_id,
                action_type="create_content_for_offer",
                title=f"No content for offer: {offer.name[:50]}",
                description=f"Active offer with ${offer.payout_amount or 0:.2f} payout has no content. "
                           f"Create content to start earning.",
                category="monetization",
                priority="medium",
                brand_id=brand_id,
                entity_type="offer",
                entity_id=offer.id,
                source_module="monetization_bridge",
            )
            actions_created.append({"type": "orphan_offer", "action_id": str(action.id)})

    await db.flush()

    logger.info(
        "monetization_bridge.actions_surfaced",
        brand_id=str(brand_id),
        actions_created=len(actions_created),
    )

    return actions_created


# ── Revenue Attribution from Webhooks ──────────────────────────────────

async def attribute_revenue_event(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    revenue: float,
    event_type: str = "conversion",
    source: str = "webhook",
    offer_id: Optional[uuid.UUID] = None,
    content_item_id: Optional[uuid.UUID] = None,
    metadata: Optional[dict] = None,
) -> AttributionEvent:
    """Create an attribution event linking revenue to content and offers.

    This is the bridge between webhook-ingested revenue and the
    content/offer attribution model. Called by webhook handlers
    when they can identify the content/offer that drove revenue.
    """
    # Try to infer offer from content if not provided
    if content_item_id and not offer_id:
        item = (await db.execute(
            select(ContentItem.offer_id).where(ContentItem.id == content_item_id)
        )).scalar()
        if item:
            offer_id = item

    event = AttributionEvent(
        brand_id=brand_id,
        content_item_id=content_item_id,
        offer_id=offer_id,
        event_type=event_type,
        event_value=revenue,
        attribution_model="last_click",
        metadata_json=metadata or {"source": source},
    )
    db.add(event)
    await db.flush()

    org_id = (await db.execute(
        select(Brand.organization_id).where(Brand.id == brand_id)
    )).scalar()

    await emit_event(
        db, domain="monetization", event_type="revenue.attributed",
        summary=f"Revenue ${revenue:.2f} attributed ({source})"
               + (f" → offer {offer_id}" if offer_id else "")
               + (f" → content {content_item_id}" if content_item_id else ""),
        org_id=org_id, brand_id=brand_id,
        entity_type="attribution_event", entity_id=event.id,
        details={
            "revenue": revenue,
            "source": source,
            "offer_id": str(offer_id) if offer_id else None,
            "content_item_id": str(content_item_id) if content_item_id else None,
        },
    )

    return event
