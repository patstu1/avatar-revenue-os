"""Monetization Hub API — real revenue operations for the operator.

This is the revenue operating surface. It exposes the canonical ledger,
affiliate/sponsor/service pipelines, and attribution management for the
actual business model (not SaaS billing).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.services import monetization_bridge as mon

router = APIRouter()


# ── Canonical Ledger ──────────────────────────────────────────────────

@router.get("/monetization-hub/ledger")
async def get_ledger_entries(
    current_user: CurrentUser, db: DBSession,
    brand_id: uuid.UUID = Query(...),
    source_type: str = Query(None, description="affiliate_commission, sponsor_payment, service_fee, product_sale, ad_revenue"),
    payment_state: str = Query(None, description="pending, confirmed, paid, disputed, refunded"),
    limit: int = Query(50, le=200), offset: int = Query(0),
):
    """Paginated canonical revenue ledger entries."""
    return await mon.get_ledger_entries(
        db, brand_id, source_type=source_type, payment_state=payment_state, limit=limit, offset=offset,
    )


@router.get("/monetization-hub/ledger/summary")
async def get_ledger_summary(
    current_user: CurrentUser, db: DBSession,
    brand_id: uuid.UUID = Query(...),
    days: int = Query(30, le=365),
):
    """Revenue summary: totals by source type, payment state, and period."""
    return await mon.get_ledger_summary(db, brand_id, days=days)


@router.post("/monetization-hub/ledger/record")
async def record_manual_revenue(
    current_user: OperatorUser, db: DBSession,
    brand_id: uuid.UUID = Query(...),
    gross_amount: float = Query(...),
    revenue_source_type: str = Query(..., description="sponsor_payment, service_fee, consulting_fee, product_sale, etc."),
    description: str = Query(None),
    offer_id: uuid.UUID = Query(None),
    content_item_id: uuid.UUID = Query(None),
    sponsor_id: uuid.UUID = Query(None),
):
    """Manual ledger entry for offline revenue (checks, wire transfers, cash)."""
    source_map = {
        "affiliate_commission": mon.record_affiliate_commission_to_ledger,
        "sponsor_payment": mon.record_sponsor_payment_to_ledger,
        "service_fee": mon.record_service_payment_to_ledger,
        "consulting_fee": mon.record_service_payment_to_ledger,
        "product_sale": mon.record_product_sale_to_ledger,
        "digital_product": mon.record_product_sale_to_ledger,
        "ad_revenue": mon.record_ad_revenue_to_ledger,
    }
    fn = source_map.get(revenue_source_type)
    if not fn:
        raise HTTPException(400, f"Unknown revenue source type: {revenue_source_type}")

    kwargs = {"db": db, "brand_id": brand_id, "gross_amount": gross_amount,
              "description": description, "payment_processor": "manual"}
    if offer_id:
        kwargs["offer_id"] = offer_id
    if content_item_id:
        kwargs["content_item_id"] = content_item_id
    if hasattr(fn, '__code__') and 'sponsor_id' in fn.__code__.co_varnames and sponsor_id:
        kwargs["sponsor_id"] = sponsor_id

    entry = await fn(**kwargs)
    await db.commit()
    return {"status": "recorded", "ledger_id": str(entry.id), "gross_amount": gross_amount}


@router.post("/monetization-hub/ledger/mark-paid")
async def mark_ledger_paid(
    current_user: OperatorUser, db: DBSession,
    ledger_id: uuid.UUID = Query(...),
):
    """Mark a pending ledger entry as paid."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    from packages.db.models.revenue_ledger import RevenueLedgerEntry

    entry = (await db.execute(
        select(RevenueLedgerEntry).where(RevenueLedgerEntry.id == ledger_id)
    )).scalar_one_or_none()
    if not entry:
        raise HTTPException(404, "Ledger entry not found")
    entry.payment_state = "paid"
    entry.paid_out_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "paid", "ledger_id": str(ledger_id)}


# ── Revenue State ──────────────────────────────────────────────────

@router.get("/monetization-hub/revenue-state")
async def get_brand_revenue_state(
    current_user: CurrentUser, db: DBSession,
    brand_id: uuid.UUID = Query(...),
):
    """Real-time revenue state from the canonical ledger."""
    return await mon.get_brand_revenue_state(db, brand_id)


# ── Content ↔ Offer ──────────────────────────────────────────────────

@router.get("/monetization-hub/content-offers")
async def get_content_with_offers(
    current_user: CurrentUser, db: DBSession,
    brand_id: uuid.UUID = Query(...), limit: int = Query(50, le=200),
):
    """Content items with their assigned offers."""
    return await mon.get_content_with_offers(db, brand_id, limit=limit)


@router.post("/monetization-hub/assign-offer")
async def assign_offer_to_content(
    current_user: OperatorUser, db: DBSession,
    content_id: uuid.UUID = Query(...), offer_id: uuid.UUID = Query(...),
):
    """Link an offer to content for attribution tracking."""
    try:
        await mon.assign_offer_to_content(
            db, content_id, offer_id, org_id=current_user.organization_id, actor_id=str(current_user.id),
        )
        await db.commit()
        return {"status": "assigned", "content_id": str(content_id), "offer_id": str(offer_id)}
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Attribution ──────────────────────────────────────────────────

@router.post("/monetization-hub/attribute-revenue")
async def attribute_revenue(
    current_user: OperatorUser, db: DBSession,
    brand_id: uuid.UUID = Query(...), revenue: float = Query(...),
    source: str = Query("manual"), offer_id: uuid.UUID = Query(None),
    content_item_id: uuid.UUID = Query(None),
):
    """Attribute revenue to content/offer. Writes to both AttributionEvent and canonical ledger."""
    result = await mon.attribute_revenue_event(
        db, brand_id, revenue=revenue, source=source, offer_id=offer_id, content_item_id=content_item_id,
    )
    await db.commit()
    return {"status": "attributed", "ledger_id": str(result["ledger_entry"].id), "revenue": revenue}


@router.get("/monetization-hub/unattributed")
async def get_unattributed_revenue(
    current_user: CurrentUser, db: DBSession,
    brand_id: uuid.UUID = Query(...), limit: int = Query(20),
):
    """Revenue entries that haven't been linked to content or offers."""
    return await mon.get_ledger_entries(
        db, brand_id, payment_state=None, source_type=None, limit=limit,
    )


# ── Surface Actions ──────────────────────────────────────────────────

@router.post("/monetization-hub/surface-actions")
async def surface_monetization_actions(
    current_user: CurrentUser, db: DBSession,
    brand_id: uuid.UUID = Query(...),
):
    """Scan for monetization gaps and create operator actions."""
    actions = await mon.surface_monetization_actions(db, current_user.organization_id, brand_id)
    await db.commit()
    return {"actions_created": len(actions), "actions": actions}
