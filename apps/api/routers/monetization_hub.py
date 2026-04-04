"""Monetization Hub API — unified monetization surface for the operator.

Bridges offers, content, revenue tracking, and attribution into
actionable endpoints for the control layer.
"""
import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.services import monetization_bridge as mon_bridge

router = APIRouter()


@router.get("/monetization-hub/revenue-state")
async def get_brand_revenue_state(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(..., description="Brand to get revenue state for"),
):
    """Real-time revenue state for a brand.

    Aggregates platform revenue, attribution events, creator revenue,
    and content monetization rate into one view.
    """
    return await mon_bridge.get_brand_revenue_state(db, brand_id)


@router.get("/monetization-hub/content-offers")
async def get_content_with_offers(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(...),
    limit: int = Query(50, le=200),
):
    """Content items with their assigned offers.

    Shows which content promotes which offer, enabling revenue tracking.
    """
    return await mon_bridge.get_content_with_offers(db, brand_id, limit=limit)


@router.post("/monetization-hub/assign-offer")
async def assign_offer_to_content(
    current_user: OperatorUser,
    db: DBSession,
    content_id: uuid.UUID = Query(...),
    offer_id: uuid.UUID = Query(...),
):
    """Assign an offer to a content item.

    Links the offer to the content for revenue attribution tracking.
    """
    try:
        item = await mon_bridge.assign_offer_to_content(
            db, content_id, offer_id,
            org_id=current_user.organization_id,
            actor_id=str(current_user.id),
        )
        await db.commit()
        return {
            "status": "assigned",
            "content_id": str(content_id),
            "offer_id": str(offer_id),
            "title": item.title,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/monetization-hub/attribute-revenue")
async def attribute_revenue(
    current_user: OperatorUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(...),
    revenue: float = Query(..., description="Revenue amount"),
    event_type: str = Query("conversion"),
    source: str = Query("manual"),
    offer_id: uuid.UUID = Query(None),
    content_item_id: uuid.UUID = Query(None),
):
    """Manually attribute a revenue event.

    For offline conversions or events that can't be captured via webhooks.
    """
    event = await mon_bridge.attribute_revenue_event(
        db, brand_id,
        revenue=revenue,
        event_type=event_type,
        source=source,
        offer_id=offer_id,
        content_item_id=content_item_id,
    )
    await db.commit()
    return {
        "status": "attributed",
        "event_id": str(event.id),
        "revenue": revenue,
    }


@router.post("/monetization-hub/surface-actions")
async def surface_monetization_actions(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(...),
):
    """Scan monetization state and create operator actions.

    Identifies unmonetized content, orphan offers, revenue blockers,
    and high-value opportunities.
    """
    org_id = current_user.organization_id
    actions = await mon_bridge.surface_monetization_actions(db, org_id, brand_id)
    await db.commit()
    return {"actions_created": len(actions), "actions": actions}
