"""Intelligence Hub API — unified intelligence surface for the control layer.

Aggregates all intelligence subsystem outputs into actionable endpoints
that the operator can use to understand what the system knows, what it
recommends, and what it has learned.
"""

import uuid

from fastapi import APIRouter, Query

from apps.api.deps import CurrentUser, DBSession
from apps.api.services import intelligence_bridge as intel

router = APIRouter()


@router.get("/intelligence/summary")
async def get_intelligence_summary(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(None, description="Filter by brand (optional)"),
):
    """Unified intelligence summary — everything the system knows.

    Returns active brain decisions, winning/losing patterns, experiments,
    suppression rules, failure families, kill ledger, and opportunities.
    """
    org_id = current_user.organization_id
    return await intel.get_intelligence_summary(db, org_id, brand_id)


@router.get("/intelligence/generation-context")
async def get_generation_context(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(..., description="Brand to get intelligence for"),
    platform: str = Query(None, description="Filter by platform"),
):
    """Intelligence context for content generation.

    Returns the winning patterns, losing patterns, suppression rules,
    and promoted rules that should influence the next generation.
    """
    return await intel.get_generation_intelligence(
        db,
        brand_id,
        platform=platform,
    )


@router.get("/intelligence/kill-check")
async def check_kill_ledger(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(...),
    entity_type: str = Query(None),
    pattern_type: str = Query(None),
    pattern_key: str = Query(None),
):
    """Check the kill ledger before attempting an action.

    Returns whether the action is blocked and why.
    """
    return await intel.check_kill_ledger(
        db,
        brand_id,
        entity_type=entity_type,
        pattern_type=pattern_type,
        pattern_key=pattern_key,
    )


@router.post("/intelligence/surface-actions")
async def surface_intelligence_actions(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(...),
):
    """Scan intelligence outputs and create operator actions.

    Translates brain decisions, pattern decay, experiment winners,
    and failure patterns into actionable items in the control layer.
    """
    org_id = current_user.organization_id
    actions = await intel.surface_intelligence_actions(db, org_id, brand_id)
    await db.commit()
    return {"actions_created": len(actions), "actions": actions}
