"""Conversion Tracker — tracks the click → landing → purchase chain.

Generates UTM parameters per content+offer, records click events,
and links conversions back to the content that drove them.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.publishing import AttributionEvent

logger = structlog.get_logger()


def generate_tracking_params(
    content_id: uuid.UUID, offer_id: uuid.UUID,
    *, platform: str = "unknown", campaign: str = "auto",
) -> dict:
    """Generate UTM parameters + tracking ID for content→offer attribution."""
    tracking_id = hashlib.sha256(f"{content_id}:{offer_id}:{platform}".encode()).hexdigest()[:16]

    return {
        "tracking_id": tracking_id,
        "utm_source": platform,
        "utm_medium": "content",
        "utm_campaign": campaign,
        "utm_content": str(content_id)[:8],
        "utm_term": str(offer_id)[:8],
        "full_url_params": f"?utm_source={platform}&utm_medium=content&utm_campaign={campaign}&utm_content={str(content_id)[:8]}&ref={tracking_id}",
    }


async def record_click(
    db: AsyncSession, brand_id: uuid.UUID,
    *, tracking_id: str, content_item_id: uuid.UUID | None = None,
    offer_id: uuid.UUID | None = None, platform: str | None = None,
) -> AttributionEvent:
    """Record a click event in the attribution chain."""
    event = AttributionEvent(
        brand_id=brand_id,
        content_item_id=content_item_id,
        offer_id=offer_id,
        event_type="click",
        event_value=0,
        attribution_model="last_click",
        platform=platform,
        tracking_id=tracking_id,
        raw_event={"tracking_id": tracking_id, "timestamp": datetime.now(timezone.utc).isoformat()},
    )
    db.add(event)
    await db.flush()
    return event


async def record_conversion(
    db: AsyncSession, brand_id: uuid.UUID,
    *, tracking_id: str, revenue: float,
    content_item_id: uuid.UUID | None = None,
    offer_id: uuid.UUID | None = None,
) -> dict:
    """Record a conversion event and link it back to the click chain."""
    # Find the click event that started this chain
    click = (await db.execute(
        select(AttributionEvent).where(
            AttributionEvent.brand_id == brand_id,
            AttributionEvent.tracking_id == tracking_id,
            AttributionEvent.event_type == "click",
        ).order_by(AttributionEvent.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    # Inherit content/offer from click if not provided
    if click:
        content_item_id = content_item_id or click.content_item_id
        offer_id = offer_id or click.offer_id

    conversion = AttributionEvent(
        brand_id=brand_id,
        content_item_id=content_item_id,
        offer_id=offer_id,
        event_type="conversion",
        event_value=revenue,
        attribution_model="last_click",
        tracking_id=tracking_id,
        raw_event={"tracking_id": tracking_id, "revenue": revenue,
                    "click_id": str(click.id) if click else None},
    )
    db.add(conversion)
    await db.flush()

    # Also write to canonical ledger
    from apps.api.services.monetization_bridge import attribute_revenue_event
    result = await attribute_revenue_event(
        db, brand_id, revenue=revenue,
        source="conversion_tracker",
        offer_id=offer_id, content_item_id=content_item_id,
    )

    return {
        "conversion_id": str(conversion.id),
        "click_linked": click is not None,
        "content_id": str(content_item_id) if content_item_id else None,
        "offer_id": str(offer_id) if offer_id else None,
        "revenue": revenue,
        "ledger_entry_id": str(result["ledger_entry"].id) if result.get("ledger_entry") else None,
    }


async def get_conversion_chain(
    db: AsyncSession, brand_id: uuid.UUID, tracking_id: str,
) -> list[dict]:
    """Get the full click → conversion chain for a tracking ID."""
    events = (await db.execute(
        select(AttributionEvent).where(
            AttributionEvent.brand_id == brand_id,
            AttributionEvent.tracking_id == tracking_id,
        ).order_by(AttributionEvent.created_at)
    )).scalars().all()

    return [
        {"id": str(e.id), "type": e.event_type, "value": e.event_value,
         "content_id": str(e.content_item_id) if e.content_item_id else None,
         "offer_id": str(e.offer_id) if e.offer_id else None,
         "created_at": e.created_at.isoformat() if e.created_at else None}
        for e in events
    ]
