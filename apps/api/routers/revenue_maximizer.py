"""Revenue Maximizer API — the money command center.

8 endpoints exposing all 7 revenue engines plus the unified command center view.
"""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Query
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.services import revenue_maximizer as rev

router = APIRouter()


@router.get("/revenue/fit-scores")
async def get_fit_scores(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Creator monetization fit across 10 paths."""
    return await rev.compute_creator_monetization_fit(db, brand_id)


@router.get("/revenue/opportunities")
async def get_opportunities(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Ranked revenue opportunities with expected upside."""
    return await rev.detect_revenue_opportunities(db, brand_id)


@router.get("/revenue/allocation")
async def get_allocation(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Where effort should go, ranked by ROI."""
    return await rev.compute_revenue_allocation(db, brand_id)


@router.get("/revenue/suppressions")
async def get_suppressions(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """What to stop doing — weak offers, dead patterns, low-ROI paths."""
    return await rev.compute_suppression_targets(db, brand_id)


@router.get("/revenue/memory")
async def get_memory(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """What has worked and why — patterns, rules, learning entries."""
    return await rev.get_revenue_memory(db, brand_id)


@router.get("/revenue/mix")
async def get_mix(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Current vs recommended monetization mix."""
    return await rev.compute_monetization_mix(db, brand_id)


@router.get("/revenue/next-actions")
async def get_next_actions(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Top next-best revenue actions ranked by expected value."""
    return await rev.get_next_best_revenue_actions(db, brand_id, current_user.organization_id)


@router.get("/revenue/command-center")
async def get_command_center(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """All-in-one revenue maximization view — everything in one call."""
    return await rev.get_revenue_command_center(db, brand_id, current_user.organization_id)


@router.post("/revenue/auto-surface-actions")
async def auto_surface(current_user: OperatorUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Auto-create operator actions from revenue intelligence."""
    actions = await rev.auto_surface_revenue_actions(db, current_user.organization_id, brand_id)
    await db.commit()
    return {"actions_created": len(actions), "actions": actions}
