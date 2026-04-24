"""Monetization Bridge — the canonical revenue integration layer.

This service connects the real business model (affiliate, sponsor, service,
product, lead gen) to the operating system through the canonical revenue ledger.

Every dollar resolves into RevenueLedgerEntry, regardless of source.
No fragmented money truth. One source of truth.

Revenue source types:
- affiliate_commission: Affiliate offer earnings via tracking links
- sponsor_payment: Sponsor deal milestone payments
- service_fee / consulting_fee: Service/consulting revenue
- product_sale / digital_product: Product sales
- ad_revenue: Platform ad revenue (YouTube, TikTok, etc.)
- lead_gen_fee: Lead/referral commissions
- refund / chargeback / adjustment: Reversals and corrections
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_action, emit_event
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.creator_revenue import CreatorRevenueBlocker
from packages.db.models.offers import Offer
from packages.db.models.publishing import AttributionEvent, PerformanceMetric
from packages.db.models.revenue_ledger import RevenueLedgerEntry

logger = structlog.get_logger()


# ── Offer Selection ─────────────────────────────────────────────────


async def select_best_offer_for_content(
    db: AsyncSession,
    brand_id: uuid.UUID,
) -> Offer | None:
    """Pick the highest-value active offer for a brand.

    Weighted by EPC (70%) and priority (30%, scaled by 0.03):
      score = epc * 0.7 + priority * 0.03

    Priority 10 → +0.3 score, priority 0 → +0. An offer with EPC $2.00 and
    priority 10 scores 1.70; one with EPC $1.00 and priority 0 scores 0.70.

    Returns None when the brand has zero active offers.
    """
    offer_score = Offer.epc * 0.7 + Offer.priority * 0.03
    return (
        await db.execute(
            select(Offer)
            .where(
                Offer.brand_id == brand_id,
                Offer.is_active.is_(True),
            )
            .order_by(offer_score.desc().nullslast())
            .limit(1)
        )
    ).scalar_one_or_none()


# ── Offer ↔ Content Linkage (kept from Phase 4) ──────────────────────


async def assign_offer_to_content(
    db: AsyncSession,
    content_id: uuid.UUID,
    offer_id: uuid.UUID,
    *,
    org_id: uuid.UUID | None = None,
    actor_id: str | None = None,
) -> ContentItem:
    """Link an offer to a content item for revenue attribution."""
    item = (await db.execute(select(ContentItem).where(ContentItem.id == content_id))).scalar_one_or_none()
    if not item:
        raise ValueError(f"ContentItem {content_id} not found")
    offer = (await db.execute(select(Offer).where(Offer.id == offer_id))).scalar_one_or_none()
    if not offer:
        raise ValueError(f"Offer {offer_id} not found")

    item.offer_id = offer_id
    item.monetization_method = (
        offer.monetization_method.value
        if hasattr(offer.monetization_method, "value")
        else str(offer.monetization_method)
        if offer.monetization_method
        else None
    )

    if not org_id:
        org_id = (await db.execute(select(Brand.organization_id).where(Brand.id == item.brand_id))).scalar()

    await emit_event(
        db,
        domain="monetization",
        event_type="offer.assigned_to_content",
        summary=f"Offer '{offer.name[:40]}' assigned to content '{item.title[:40]}'",
        org_id=org_id,
        brand_id=item.brand_id,
        entity_type="content_item",
        entity_id=content_id,
        details={"offer_id": str(offer_id), "offer_name": offer.name},
    )
    await db.flush()
    return item


# ══════════════════════════════════════════════════════════════════════
# CANONICAL LEDGER WRITE FUNCTIONS
# Every revenue path resolves through one of these functions.
# ══════════════════════════════════════════════════════════════════════


async def record_affiliate_commission_to_ledger(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    gross_amount: float,
    offer_id: uuid.UUID | None = None,
    content_item_id: uuid.UUID | None = None,
    creator_account_id: uuid.UUID | None = None,
    affiliate_link_id: uuid.UUID | None = None,
    source_object_id: uuid.UUID | None = None,
    net_amount: float | None = None,
    platform_fee: float = 0.0,
    external_transaction_id: str | None = None,
    payment_processor: str | None = None,
    description: str | None = None,
    metadata: dict | None = None,
) -> RevenueLedgerEntry:
    """Record an affiliate commission to the canonical ledger."""
    entry = RevenueLedgerEntry(
        revenue_source_type="affiliate_commission",
        source_object_id=source_object_id,
        source_object_table="af_commissions" if source_object_id else None,
        brand_id=brand_id,
        offer_id=offer_id,
        content_item_id=content_item_id,
        creator_account_id=creator_account_id,
        affiliate_link_id=affiliate_link_id,
        gross_amount=gross_amount,
        net_amount=net_amount if net_amount is not None else gross_amount - platform_fee,
        platform_fee=platform_fee,
        currency="USD",
        payment_state="pending",
        attribution_state="auto_attributed" if content_item_id and offer_id else "unattributed",
        external_transaction_id=external_transaction_id,
        payment_processor=payment_processor or "affiliate_network",
        description=description or f"Affiliate commission: ${gross_amount:.2f}",
        metadata_json=metadata or {},
    )
    db.add(entry)
    await db.flush()

    org_id = (await db.execute(select(Brand.organization_id).where(Brand.id == brand_id))).scalar()
    await emit_event(
        db,
        domain="monetization",
        event_type="ledger.affiliate_commission",
        summary=f"Affiliate commission: ${gross_amount:.2f}" + (f" via offer {offer_id}" if offer_id else ""),
        org_id=org_id,
        brand_id=brand_id,
        entity_type="revenue_ledger",
        entity_id=entry.id,
        details={"gross": gross_amount, "source": "affiliate"},
    )
    return entry


async def record_sponsor_payment_to_ledger(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    gross_amount: float,
    sponsor_id: uuid.UUID | None = None,
    source_object_id: uuid.UUID | None = None,
    content_item_id: uuid.UUID | None = None,
    creator_account_id: uuid.UUID | None = None,
    campaign_id: uuid.UUID | None = None,
    net_amount: float | None = None,
    platform_fee: float = 0.0,
    payment_state: str = "pending",
    external_transaction_id: str | None = None,
    payment_processor: str | None = None,
    description: str | None = None,
    metadata: dict | None = None,
) -> RevenueLedgerEntry:
    """Record a sponsor deal payment to the canonical ledger."""
    entry = RevenueLedgerEntry(
        revenue_source_type="sponsor_payment",
        source_object_id=source_object_id,
        source_object_table="sponsor_opportunities" if source_object_id else None,
        brand_id=brand_id,
        sponsor_id=sponsor_id,
        content_item_id=content_item_id,
        creator_account_id=creator_account_id,
        campaign_id=campaign_id,
        gross_amount=gross_amount,
        net_amount=net_amount if net_amount is not None else gross_amount - platform_fee,
        platform_fee=platform_fee,
        currency="USD",
        payment_state=payment_state,
        attribution_state="auto_attributed" if sponsor_id else "manually_attributed",
        external_transaction_id=external_transaction_id,
        payment_processor=payment_processor or "direct",
        description=description or f"Sponsor payment: ${gross_amount:.2f}",
        metadata_json=metadata or {},
    )
    db.add(entry)
    await db.flush()

    org_id = (await db.execute(select(Brand.organization_id).where(Brand.id == brand_id))).scalar()
    await emit_event(
        db,
        domain="monetization",
        event_type="ledger.sponsor_payment",
        summary=f"Sponsor payment: ${gross_amount:.2f}",
        org_id=org_id,
        brand_id=brand_id,
        entity_type="revenue_ledger",
        entity_id=entry.id,
        details={"gross": gross_amount, "source": "sponsor", "sponsor_id": str(sponsor_id) if sponsor_id else None},
    )

    try:
        from apps.api.services.pipeline_closer import handle_payment_received

        await handle_payment_received(db, entry)
    except Exception as e:
        logger.warning("pipeline_closer.failed", error=str(e))

    return entry


async def record_service_payment_to_ledger(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    gross_amount: float,
    source_object_id: uuid.UUID | None = None,
    net_amount: float | None = None,
    platform_fee: float = 0.0,
    external_transaction_id: str | None = None,
    payment_processor: str = "stripe",
    webhook_ref: str | None = None,
    content_item_id: uuid.UUID | None = None,
    creator_account_id: uuid.UUID | None = None,
    description: str | None = None,
    metadata: dict | None = None,
    auto_close_pipeline: bool = True,
) -> RevenueLedgerEntry:
    """Record a service/consulting payment to the canonical ledger.

    When auto_close_pipeline=True, also triggers pipeline closure:
    deal stage update, success memory, post-close actions.
    """
    entry = RevenueLedgerEntry(
        revenue_source_type="service_fee",
        source_object_id=source_object_id,
        source_object_table="high_ticket_deals" if source_object_id else None,
        brand_id=brand_id,
        content_item_id=content_item_id,
        creator_account_id=creator_account_id,
        gross_amount=gross_amount,
        net_amount=net_amount if net_amount is not None else gross_amount - platform_fee,
        platform_fee=platform_fee,
        currency="USD",
        payment_state="confirmed",
        attribution_state="manually_attributed",
        external_transaction_id=external_transaction_id,
        payment_processor=payment_processor,
        webhook_ref=webhook_ref,
        description=description or f"Service payment: ${gross_amount:.2f}",
        metadata_json=metadata or {},
    )
    db.add(entry)
    await db.flush()

    org_id = (await db.execute(select(Brand.organization_id).where(Brand.id == brand_id))).scalar()
    await emit_event(
        db,
        domain="monetization",
        event_type="ledger.service_payment",
        summary=f"Service payment: ${gross_amount:.2f} via {payment_processor}",
        org_id=org_id,
        brand_id=brand_id,
        entity_type="revenue_ledger",
        entity_id=entry.id,
        details={"gross": gross_amount, "source": "service", "processor": payment_processor},
    )

    # Auto-close pipeline: update deal stage, create memory, trigger follow-up
    if auto_close_pipeline:
        try:
            from apps.api.services.pipeline_closer import handle_payment_received

            await handle_payment_received(db, entry)
        except Exception as e:
            logger.warning("pipeline_closer.failed", error=str(e))

    return entry


async def record_product_sale_to_ledger(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    gross_amount: float,
    source_object_id: uuid.UUID | None = None,
    offer_id: uuid.UUID | None = None,
    content_item_id: uuid.UUID | None = None,
    net_amount: float | None = None,
    platform_fee: float = 0.0,
    external_transaction_id: str | None = None,
    payment_processor: str = "shopify",
    webhook_ref: str | None = None,
    description: str | None = None,
    metadata: dict | None = None,
) -> RevenueLedgerEntry:
    """Record a product sale to the canonical ledger."""
    entry = RevenueLedgerEntry(
        revenue_source_type="product_sale",
        source_object_id=source_object_id,
        source_object_table="product_launches" if source_object_id else None,
        brand_id=brand_id,
        offer_id=offer_id,
        content_item_id=content_item_id,
        gross_amount=gross_amount,
        net_amount=net_amount if net_amount is not None else gross_amount - platform_fee,
        platform_fee=platform_fee,
        currency="USD",
        payment_state="confirmed",
        attribution_state="auto_attributed" if content_item_id or offer_id else "unattributed",
        external_transaction_id=external_transaction_id,
        payment_processor=payment_processor,
        webhook_ref=webhook_ref,
        description=description or f"Product sale: ${gross_amount:.2f}",
        metadata_json=metadata or {},
    )
    db.add(entry)
    await db.flush()

    org_id = (await db.execute(select(Brand.organization_id).where(Brand.id == brand_id))).scalar()
    await emit_event(
        db,
        domain="monetization",
        event_type="ledger.product_sale",
        summary=f"Product sale: ${gross_amount:.2f} via {payment_processor}",
        org_id=org_id,
        brand_id=brand_id,
        entity_type="revenue_ledger",
        entity_id=entry.id,
        details={"gross": gross_amount, "source": "product"},
    )
    return entry


async def record_ad_revenue_to_ledger(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    gross_amount: float,
    content_item_id: uuid.UUID | None = None,
    creator_account_id: uuid.UUID | None = None,
    platform_fee: float = 0.0,
    payment_processor: str | None = None,
    description: str | None = None,
    metadata: dict | None = None,
) -> RevenueLedgerEntry:
    """Record platform ad revenue to the canonical ledger."""
    entry = RevenueLedgerEntry(
        revenue_source_type="ad_revenue",
        brand_id=brand_id,
        content_item_id=content_item_id,
        creator_account_id=creator_account_id,
        gross_amount=gross_amount,
        net_amount=gross_amount - platform_fee,
        platform_fee=platform_fee,
        currency="USD",
        payment_state="confirmed",
        attribution_state="auto_attributed" if content_item_id else "unattributed",
        payment_processor=payment_processor or "platform",
        description=description or f"Ad revenue: ${gross_amount:.2f}",
        metadata_json=metadata or {},
    )
    db.add(entry)
    await db.flush()
    return entry


async def record_refund_to_ledger(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    refund_amount: float,
    refund_of_id: uuid.UUID,
    reason: str | None = None,
    webhook_ref: str | None = None,
    metadata: dict | None = None,
) -> RevenueLedgerEntry:
    """Record a refund as a negative ledger entry linked to the original."""
    original = (
        await db.execute(select(RevenueLedgerEntry).where(RevenueLedgerEntry.id == refund_of_id))
    ).scalar_one_or_none()

    entry = RevenueLedgerEntry(
        revenue_source_type="refund",
        source_object_id=refund_of_id,
        source_object_table="revenue_ledger",
        brand_id=brand_id,
        offer_id=original.offer_id if original else None,
        content_item_id=original.content_item_id if original else None,
        gross_amount=-abs(refund_amount),
        net_amount=-abs(refund_amount),
        currency="USD",
        payment_state="confirmed",
        attribution_state=original.attribution_state if original else "unattributed",
        is_refund=True,
        refund_of_id=refund_of_id,
        dispute_reason=reason,
        webhook_ref=webhook_ref,
        description=f"Refund: -${abs(refund_amount):.2f}" + (f" ({reason})" if reason else ""),
        metadata_json=metadata or {},
    )
    db.add(entry)

    if original:
        original.payment_state = "refunded"

    await db.flush()
    return entry


# ══════════════════════════════════════════════════════════════════════
# LEDGER QUERIES
# ══════════════════════════════════════════════════════════════════════


async def get_ledger_summary(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    days: int = 30,
) -> dict:
    """Aggregated revenue summary from the canonical ledger."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Total by source type
    by_source_q = await db.execute(
        select(RevenueLedgerEntry.revenue_source_type, func.sum(RevenueLedgerEntry.gross_amount))
        .where(
            RevenueLedgerEntry.brand_id == brand_id,
            RevenueLedgerEntry.occurred_at >= cutoff,
            RevenueLedgerEntry.is_active.is_(True),
        )
        .group_by(RevenueLedgerEntry.revenue_source_type)
    )
    by_source = {str(row[0]): float(row[1] or 0) for row in by_source_q.all()}

    # Total by payment state
    by_state_q = await db.execute(
        select(RevenueLedgerEntry.payment_state, func.sum(RevenueLedgerEntry.gross_amount))
        .where(
            RevenueLedgerEntry.brand_id == brand_id,
            RevenueLedgerEntry.occurred_at >= cutoff,
            RevenueLedgerEntry.is_active.is_(True),
        )
        .group_by(RevenueLedgerEntry.payment_state)
    )
    by_state = {str(row[0]): float(row[1] or 0) for row in by_state_q.all()}

    # Grand totals
    total_gross = sum(v for v in by_source.values())
    confirmed = by_state.get("confirmed", 0) + by_state.get("paid", 0)
    pending = by_state.get("pending", 0)
    disputed = sum(v for k, v in by_state.items() if k in ("disputed",))

    # Entry count
    entry_count = (
        await db.execute(
            select(func.count())
            .select_from(RevenueLedgerEntry)
            .where(RevenueLedgerEntry.brand_id == brand_id, RevenueLedgerEntry.occurred_at >= cutoff)
        )
    ).scalar() or 0

    # Unattributed count
    unattributed = (
        await db.execute(
            select(func.count())
            .select_from(RevenueLedgerEntry)
            .where(
                RevenueLedgerEntry.brand_id == brand_id,
                RevenueLedgerEntry.attribution_state == "unattributed",
                RevenueLedgerEntry.occurred_at >= cutoff,
                RevenueLedgerEntry.is_refund.is_(False),
            )
        )
    ).scalar() or 0

    return {
        "period_days": days,
        "total_gross": total_gross,
        "total_confirmed": confirmed,
        "total_pending": pending,
        "total_disputed": disputed,
        "by_source": by_source,
        "by_state": by_state,
        "entry_count": entry_count,
        "unattributed_count": unattributed,
    }


async def get_ledger_entries(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    source_type: str | None = None,
    payment_state: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Paginated ledger entries with optional filters."""
    query = select(RevenueLedgerEntry).where(
        RevenueLedgerEntry.brand_id == brand_id, RevenueLedgerEntry.is_active.is_(True)
    )
    if source_type:
        query = query.where(RevenueLedgerEntry.revenue_source_type == source_type)
    if payment_state:
        query = query.where(RevenueLedgerEntry.payment_state == payment_state)
    query = query.order_by(RevenueLedgerEntry.occurred_at.desc()).offset(offset).limit(limit)

    results = (await db.execute(query)).scalars().all()
    return [
        {
            "id": str(e.id),
            "revenue_source_type": e.revenue_source_type,
            "brand_id": str(e.brand_id),
            "offer_id": str(e.offer_id) if e.offer_id else None,
            "content_item_id": str(e.content_item_id) if e.content_item_id else None,
            "creator_account_id": str(e.creator_account_id) if e.creator_account_id else None,
            "sponsor_id": str(e.sponsor_id) if e.sponsor_id else None,
            "gross_amount": e.gross_amount,
            "net_amount": e.net_amount,
            "platform_fee": e.platform_fee,
            "currency": e.currency,
            "payment_state": e.payment_state,
            "attribution_state": e.attribution_state,
            "payout_state": e.payout_state,
            "is_refund": e.is_refund,
            "description": e.description,
            "payment_processor": e.payment_processor,
            "external_transaction_id": e.external_transaction_id,
            "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in results
    ]


# ══════════════════════════════════════════════════════════════════════
# BRAND REVENUE STATE (queries ledger as primary source)
# ══════════════════════════════════════════════════════════════════════


async def get_brand_revenue_state(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Real-time revenue state from the canonical ledger."""
    now = datetime.now(timezone.utc)
    day_30 = now - timedelta(days=30)
    day_7 = now - timedelta(days=7)

    # Ledger totals (primary source of truth)
    ledger_30d = (
        await db.execute(
            select(func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0.0)).where(
                RevenueLedgerEntry.brand_id == brand_id,
                RevenueLedgerEntry.occurred_at >= day_30,
                RevenueLedgerEntry.is_active.is_(True),
            )
        )
    ).scalar() or 0.0

    ledger_7d = (
        await db.execute(
            select(func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0.0)).where(
                RevenueLedgerEntry.brand_id == brand_id,
                RevenueLedgerEntry.occurred_at >= day_7,
                RevenueLedgerEntry.is_active.is_(True),
            )
        )
    ).scalar() or 0.0

    # By source type
    by_source_q = await db.execute(
        select(RevenueLedgerEntry.revenue_source_type, func.sum(RevenueLedgerEntry.gross_amount))
        .where(
            RevenueLedgerEntry.brand_id == brand_id,
            RevenueLedgerEntry.occurred_at >= day_30,
            RevenueLedgerEntry.is_active.is_(True),
        )
        .group_by(RevenueLedgerEntry.revenue_source_type)
    )
    revenue_by_source = {str(row[0]): float(row[1] or 0) for row in by_source_q.all()}

    # Pending revenue
    pending = (
        await db.execute(
            select(func.coalesce(func.sum(RevenueLedgerEntry.gross_amount), 0.0)).where(
                RevenueLedgerEntry.brand_id == brand_id,
                RevenueLedgerEntry.payment_state == "pending",
                RevenueLedgerEntry.is_active.is_(True),
            )
        )
    ).scalar() or 0.0

    # Legacy sources (backward compat — included in totals if ledger is empty)
    legacy_revenue = (
        await db.execute(
            select(func.coalesce(func.sum(PerformanceMetric.revenue), 0.0)).where(
                PerformanceMetric.brand_id == brand_id, PerformanceMetric.created_at >= day_30
            )
        )
    ).scalar() or 0.0

    # Entity counts
    active_offers = (
        await db.execute(
            select(func.count()).select_from(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
        )
    ).scalar() or 0

    total_content = (
        await db.execute(select(func.count()).select_from(ContentItem).where(ContentItem.brand_id == brand_id))
    ).scalar() or 0

    monetized_content = (
        await db.execute(
            select(func.count())
            .select_from(ContentItem)
            .where(ContentItem.brand_id == brand_id, ContentItem.offer_id.isnot(None))
        )
    ).scalar() or 0

    total_revenue = float(ledger_30d) if float(ledger_30d) > 0 else float(legacy_revenue)

    return {
        "brand_id": str(brand_id),
        "total_revenue_30d": total_revenue,
        "total_revenue_7d": float(ledger_7d),
        "revenue_by_source": revenue_by_source,
        "revenue_pending": float(pending),
        "ledger_revenue_30d": float(ledger_30d),
        "legacy_revenue_30d": float(legacy_revenue),
        "active_offers": active_offers,
        "total_content": total_content,
        "monetized_content": monetized_content,
        "monetization_rate": round((monetized_content / total_content * 100) if total_content > 0 else 0, 1),
    }


# ══════════════════════════════════════════════════════════════════════
# ATTRIBUTION (enhanced with ledger write)
# ══════════════════════════════════════════════════════════════════════


async def attribute_revenue_event(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    revenue: float,
    event_type: str = "conversion",
    source: str = "webhook",
    offer_id: uuid.UUID | None = None,
    content_item_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> dict:
    """Create attribution event AND canonical ledger entry."""
    if content_item_id and not offer_id:
        item_offer = (await db.execute(select(ContentItem.offer_id).where(ContentItem.id == content_item_id))).scalar()
        if item_offer:
            offer_id = item_offer

    attr = AttributionEvent(
        brand_id=brand_id,
        content_item_id=content_item_id,
        offer_id=offer_id,
        event_type=event_type,
        event_value=revenue,
        attribution_model="last_click",
        raw_event=metadata or {"source": source},
    )
    db.add(attr)
    await db.flush()

    # Also write to canonical ledger
    source_map = {
        "affiliate": "affiliate_commission",
        "sponsor": "sponsor_payment",
        "service": "service_fee",
        "product": "product_sale",
        "webhook": "service_fee",
    }
    ledger_source = source_map.get(source, "service_fee")

    ledger = RevenueLedgerEntry(
        revenue_source_type=ledger_source,
        brand_id=brand_id,
        offer_id=offer_id,
        content_item_id=content_item_id,
        gross_amount=revenue,
        net_amount=revenue,
        currency="USD",
        payment_state="confirmed",
        attribution_state="auto_attributed" if offer_id else "manually_attributed",
        description=f"Attribution: ${revenue:.2f} from {source}",
        metadata_json={"attribution_event_id": str(attr.id), "source": source},
    )
    db.add(ledger)
    await db.flush()

    org_id = (await db.execute(select(Brand.organization_id).where(Brand.id == brand_id))).scalar()
    await emit_event(
        db,
        domain="monetization",
        event_type="revenue.attributed",
        summary=f"Revenue ${revenue:.2f} attributed ({source})",
        org_id=org_id,
        brand_id=brand_id,
        entity_type="revenue_ledger",
        entity_id=ledger.id,
        details={"revenue": revenue, "source": source},
    )

    return {"attribution_event": attr, "ledger_entry": ledger}


# ══════════════════════════════════════════════════════════════════════
# SURFACE MONETIZATION ACTIONS (real business model)
# ══════════════════════════════════════════════════════════════════════


async def surface_monetization_actions(
    db: AsyncSession,
    org_id: uuid.UUID,
    brand_id: uuid.UUID,
) -> list[dict]:
    """Scan monetization state and create operator actions for the real business."""
    actions_created = []

    # 1. Unmonetized published content
    unmonetized = await db.execute(
        select(ContentItem)
        .where(
            ContentItem.brand_id == brand_id,
            ContentItem.status == "published",
            ContentItem.offer_id.is_(None),
        )
        .limit(5)
    )
    for item in unmonetized.scalars().all():
        action = await emit_action(
            db,
            org_id=org_id,
            action_type="assign_offer",
            title=f"Monetize: {item.title[:50]}",
            description="Published content with no offer. Assign an offer to earn.",
            category="monetization",
            priority="medium",
            brand_id=brand_id,
            entity_type="content_item",
            entity_id=item.id,
            source_module="monetization_bridge",
        )
        actions_created.append({"type": "assign_offer", "action_id": str(action.id)})

    # 2. Unattributed revenue in ledger
    unattributed = await db.execute(
        select(RevenueLedgerEntry)
        .where(
            RevenueLedgerEntry.brand_id == brand_id,
            RevenueLedgerEntry.attribution_state == "unattributed",
            RevenueLedgerEntry.is_refund.is_(False),
            RevenueLedgerEntry.is_active.is_(True),
        )
        .limit(5)
    )
    for entry in unattributed.scalars().all():
        action = await emit_action(
            db,
            org_id=org_id,
            action_type="attribute_revenue",
            title=f"Unattributed: ${entry.gross_amount:.2f} ({entry.revenue_source_type})",
            description=f"Revenue of ${entry.gross_amount:.2f} has no content/offer attribution. Link it.",
            category="monetization",
            priority="high",
            brand_id=brand_id,
            entity_type="revenue_ledger",
            entity_id=entry.id,
            source_module="monetization_bridge",
        )
        actions_created.append({"type": "unattributed", "action_id": str(action.id)})

    # 3. Orphan offers (active but no content)
    orphan_offers = await db.execute(
        select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)).limit(20)
    )
    for offer in orphan_offers.scalars().all():
        content_count = (
            await db.execute(
                select(func.count())
                .select_from(ContentItem)
                .where(ContentItem.brand_id == brand_id, ContentItem.offer_id == offer.id)
            )
        ).scalar() or 0
        if content_count == 0:
            action = await emit_action(
                db,
                org_id=org_id,
                action_type="create_content_for_offer",
                title=f"No content for: {offer.name[:50]}",
                description=f"Active offer (${offer.payout_amount or 0:.2f} payout) has no content.",
                category="monetization",
                priority="medium",
                brand_id=brand_id,
                entity_type="offer",
                entity_id=offer.id,
                source_module="monetization_bridge",
            )
            actions_created.append({"type": "orphan_offer", "action_id": str(action.id)})

    # 4. Revenue blockers
    blockers = await db.execute(
        select(CreatorRevenueBlocker)
        .where(
            CreatorRevenueBlocker.brand_id == brand_id,
            CreatorRevenueBlocker.resolved.is_(False),
        )
        .limit(5)
    )
    for b in blockers.scalars().all():
        action = await emit_action(
            db,
            org_id=org_id,
            action_type="resolve_revenue_blocker",
            title=f"Revenue blocker: {b.blocker_type[:50] if b.blocker_type else 'unknown'}",
            description=f"Avenue: {b.avenue_type or 'N/A'}. Severity: {b.severity or 'unknown'}.",
            category="monetization",
            priority="high" if b.severity == "critical" else "medium",
            brand_id=brand_id,
            entity_type="revenue_blocker",
            entity_id=b.id,
            source_module="creator_revenue",
        )
        actions_created.append({"type": "revenue_blocker", "action_id": str(action.id)})

    await db.flush()
    return actions_created


async def get_content_with_offers(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 50) -> list[dict]:
    """Content items with their assigned offers."""
    q = await db.execute(
        select(ContentItem, Offer)
        .outerjoin(Offer, ContentItem.offer_id == Offer.id)
        .where(ContentItem.brand_id == brand_id)
        .order_by(ContentItem.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "content_id": str(row[0].id),
            "title": row[0].title,
            "status": row[0].status,
            "offer": {
                "id": str(row[1].id),
                "name": row[1].name,
                "payout_amount": float(row[1].payout_amount) if row[1].payout_amount else None,
            }
            if row[1]
            else None,
        }
        for row in q.all()
    ]
