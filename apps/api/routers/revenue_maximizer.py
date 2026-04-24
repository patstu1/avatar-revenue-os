"""Revenue Maximizer API — the complete money command center.

All 17 engines + execution + governance in one API surface.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.services import action_dispatcher
from apps.api.services import revenue_engines_extended as rev_ext
from apps.api.services import revenue_execution as rev_exec
from apps.api.services import revenue_maximizer as rev

router = APIRouter()

# ── Engines 1-7 (existing) ────────────────────────────────────────────


@router.get("/revenue/fit-scores")
async def get_fit_scores(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Engine 1: Creator monetization fit across 10 paths."""
    return await rev.compute_creator_monetization_fit(db, brand_id)


@router.get("/revenue/opportunities")
async def get_opportunities(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Engine 2: Ranked revenue opportunities with expected upside."""
    return await rev.detect_revenue_opportunities(db, brand_id)


@router.get("/revenue/allocation")
async def get_allocation(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Engine 3: Where effort should go, ranked by ROI."""
    return await rev.compute_revenue_allocation(db, brand_id)


@router.get("/revenue/suppressions")
async def get_suppressions(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Engine 4: What to stop doing."""
    return await rev.compute_suppression_targets(db, brand_id)


@router.get("/revenue/memory")
async def get_memory(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Engine 5: What has worked and why."""
    return await rev.get_revenue_memory(db, brand_id)


@router.get("/revenue/mix")
async def get_mix(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Engine 6: Current vs recommended monetization mix."""
    return await rev.compute_monetization_mix(db, brand_id)


@router.get("/revenue/next-actions")
async def get_next_actions(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Engine 7: Top next-best revenue actions ranked by expected value."""
    return await rev.get_next_best_revenue_actions(db, brand_id, current_user.organization_id)


# ── Engines 8-17 (new) ────────────────────────────────────────────────


@router.get("/revenue/simulation")
async def simulate_scenario(
    current_user: CurrentUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(...),
    scenario_type: str = Query("mix_shift"),
    target_source: str = Query(None),
    target_pct: float = Query(None),
    output_multiplier: float = Query(1.0),
):
    """Engine 8: Simulate revenue scenario before committing effort."""
    return await rev_ext.simulate_revenue_scenario(
        db,
        brand_id,
        scenario_type=scenario_type,
        target_source=target_source,
        target_pct=target_pct,
        output_multiplier=output_multiplier,
    )


@router.get("/revenue/margin-rankings")
async def get_margin_rankings(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Engine 9: True-value rankings (net > gross, margin-first)."""
    return await rev_ext.compute_margin_rankings(db, brand_id)


@router.get("/revenue/archetypes")
async def get_archetypes(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Engine 10: Creator archetype classification with fit paths."""
    return await rev_ext.classify_creator_archetypes(db, brand_id)


@router.get("/revenue/packaging")
async def get_packaging(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Engine 11: Offer packaging recommendations (entry → core → upsell)."""
    return await rev_ext.compute_packaging_recommendations(db, brand_id)


@router.get("/revenue/experiments")
async def get_experiments(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Engine 12: Revenue experiment opportunities."""
    return await rev_ext.get_experiment_opportunities(db, brand_id)


@router.get("/revenue/payout-speed")
async def get_payout_speed(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Engine 13: Payout speed intelligence by source type."""
    return await rev_ext.compute_payout_speed(db, brand_id)


@router.get("/revenue/leaks")
async def get_leaks(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Engine 14: Revenue leak detection — find and repair lost money."""
    return await rev_ext.detect_revenue_leaks(db, brand_id)


@router.get("/revenue/portfolio")
async def get_portfolio(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Engine 15: Creator portfolio allocation rankings."""
    return await rev_ext.compute_portfolio_allocation(db, brand_id)


@router.get("/revenue/compounding")
async def get_compounding(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Engine 16: Cross-platform compounding opportunities."""
    return await rev_ext.detect_compounding_opportunities(db, brand_id)


@router.get("/revenue/durability")
async def get_durability(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Engine 17: Revenue durability scoring (short-term vs lasting money)."""
    return await rev_ext.compute_durability_scores(db, brand_id)


# ── Command Center + Execution ─────────────────────────────────────────


@router.get("/revenue/command-center")
async def get_command_center(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """All-in-one revenue maximization view."""
    return await rev.get_revenue_command_center(db, brand_id, current_user.organization_id)


@router.post("/revenue/execute")
async def execute_revenue_cycle(
    current_user: OperatorUser,
    db: DBSession,
    brand_id: uuid.UUID = Query(...),
    autonomy_level: str = Query(None, description="Override: surface, assisted, or autonomous"),
):
    """Execute a full revenue action cycle with 3-tier governance."""
    result = await rev_exec.execute_revenue_actions(
        db,
        current_user.organization_id,
        brand_id,
        autonomy_override=autonomy_level,
    )
    await db.commit()
    return result


@router.get("/revenue/calibration")
async def get_calibration(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Dynamic calibration context — shows the portfolio-relative thresholds the machine uses.
    No fixed numbers. All derived from actual portfolio data."""
    return await rev.build_calibration_context(db, brand_id)


@router.post("/revenue/auto-surface-actions")
async def auto_surface(current_user: OperatorUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Auto-create operator actions from revenue intelligence."""
    actions = await rev.auto_surface_revenue_actions(db, current_user.organization_id, brand_id)
    await db.commit()
    return {"actions_created": len(actions), "actions": actions}


@router.post("/revenue/dispatch-autonomous")
async def dispatch_autonomous(
    current_user: OperatorUser,
    db: DBSession,
    dry_run: bool = Query(False, description="If true, report what would be dispatched without executing"),
    limit: int = Query(20, le=100),
):
    """Dispatch pending autonomous actions — executes real state changes."""
    result = await action_dispatcher.dispatch_autonomous_actions(
        db,
        current_user.organization_id,
        dry_run=dry_run,
        limit=limit,
    )
    await db.commit()
    return result
