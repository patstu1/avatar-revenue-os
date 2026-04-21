"""GM operating-output router (Batch 7A-WIDE) — FULL-MACHINE read surface.

Ten GET endpoints surfacing the doctrine-driven computations in
``gm_situation``. All OperatorUser-auth'd, all org-scoped, all
read-only. Zero mutations.

Endpoints:

    GET  /api/v1/gm/doctrine
    GET  /api/v1/gm/floor-status
    GET  /api/v1/gm/avenue-portfolio      (NEW — all 22 avenues)
    GET  /api/v1/gm/engine-status         (NEW — all 38 engines)
    GET  /api/v1/gm/pipeline-state
    GET  /api/v1/gm/bottlenecks
    GET  /api/v1/gm/closest-revenue
    GET  /api/v1/gm/blocking-floors
    GET  /api/v1/gm/game-plan
    GET  /api/v1/gm/ask-operator          (NEW — what GM needs from operator)
    GET  /api/v1/gm/unlock-plans          (NEW — LIVE_BUT_DORMANT unlock seq)
    GET  /api/v1/gm/startup-inspection
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Query

from apps.api.deps import DBSession, OperatorUser
from apps.api.services.gm_doctrine import (
    ACTION_CLASSES,
    ALWAYS_PLAN_AND_ASK_RULE,
    ANTI_NARROWING_RULE,
    CANONICAL_DATA_TABLES,
    CANONICAL_EVENT_TYPES,
    DORMANT_AVENUE_RULE,
    FLOOR_MONTH_1_CENTS,
    FLOOR_MONTH_12_CENTS,
    FLOORS_NOT_CEILINGS_RULE,
    FORBIDDEN_BEHAVIORS,
    GM_REVENUE_DOCTRINE,
    NO_MONEY_CAPPING_RULE,
    PILLARS,
    PRIORITY_RANK,
    REVENUE_AVENUES,
    STAGE_MACHINE,
    STATUS_FLAGS,
    STRATEGIC_ENGINES,
)
from apps.api.services.gm_situation import (
    compute_ask_operator,
    compute_avenue_portfolio,
    compute_blocking_floors,
    compute_bottlenecks,
    compute_closest_revenue,
    compute_engine_status,
    compute_floor_status,
    compute_game_plan,
    compute_pipeline_state,
    compute_unlock_plans,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/gm", tags=["GM Operating"])


# ─── Doctrine surface ────────────────────────────────────────────────


@router.get("/doctrine")
async def read_doctrine(current_user: OperatorUser):
    """Full-machine doctrine constants exposed as structured JSON."""
    return {
        "floors": {
            "month_1_cents": FLOOR_MONTH_1_CENTS,
            "month_1_usd": FLOOR_MONTH_1_CENTS / 100.0,
            "month_12_cents": FLOOR_MONTH_12_CENTS,
            "month_12_usd": FLOOR_MONTH_12_CENTS / 100.0,
        },
        "pillars": list(PILLARS),
        "status_flags": list(STATUS_FLAGS),
        "action_classes": list(ACTION_CLASSES),
        "stage_machine": STAGE_MACHINE,
        "priority_rank": list(PRIORITY_RANK),
        "revenue_avenues": REVENUE_AVENUES,
        "strategic_engines": STRATEGIC_ENGINES,
        "forbidden_behaviors": list(FORBIDDEN_BEHAVIORS),
        "canonical_data_tables": list(CANONICAL_DATA_TABLES),
        "canonical_event_types": list(CANONICAL_EVENT_TYPES),
        "doctrine_rules": {
            "anti_narrowing": ANTI_NARROWING_RULE,
            "no_money_capping": NO_MONEY_CAPPING_RULE,
            "floors_not_ceilings": FLOORS_NOT_CEILINGS_RULE,
            "always_plan_and_ask": ALWAYS_PLAN_AND_ASK_RULE,
            "dormant_avenue": DORMANT_AVENUE_RULE,
        },
        "initialization_brief_preview": GM_REVENUE_DOCTRINE[:1500] + " ...",
        "total_avenues": len(REVENUE_AVENUES),
        "total_engines": len(STRATEGIC_ENGINES),
        "total_canonical_tables": len(CANONICAL_DATA_TABLES),
    }


# ─── Operating outputs ────────────────────────────────────────────────


@router.get("/floor-status")
async def floor_status(
    current_user: OperatorUser,
    db: DBSession,
    month_index: int = Query(1, ge=1, le=24),
):
    """Trailing-30d revenue vs floor, COMBINED across all ledgers
    (payments + creator_revenue_events + per-avenue sources) with
    per-avenue breakdown."""
    return await compute_floor_status(
        db, org_id=current_user.organization_id, month_index=month_index
    )


@router.get("/avenue-portfolio")
async def avenue_portfolio(current_user: OperatorUser, db: DBSession):
    """Per-avenue status + 30d revenue + activity counts, all 22
    avenues classified live."""
    return await compute_avenue_portfolio(db, org_id=current_user.organization_id)


@router.get("/engine-status")
async def engine_status(current_user: OperatorUser, db: DBSession):
    """Per-engine row count + 30-day activity + live status, all 38 engines."""
    return await compute_engine_status(db, org_id=current_user.organization_id)


@router.get("/pipeline-state")
async def pipeline_state(current_user: OperatorUser, db: DBSession):
    """B2B-avenue stage entity counts (avenue 1 only)."""
    return await compute_pipeline_state(db, org_id=current_user.organization_id)


@router.get("/bottlenecks")
async def bottlenecks(current_user: OperatorUser, db: DBSession):
    """Stuck + overdue stage_states."""
    return await compute_bottlenecks(db, org_id=current_user.organization_id)


@router.get("/closest-revenue")
async def closest_revenue(current_user: OperatorUser, db: DBSession):
    """Multi-avenue one-action-from-money inventory."""
    return await compute_closest_revenue(db, org_id=current_user.organization_id)


@router.get("/blocking-floors")
async def blocking_floors(
    current_user: OperatorUser,
    db: DBSession,
    month_index: int = Query(1, ge=1, le=24),
):
    """Floor + in-flight potential combined with blocker_reasons."""
    return await compute_blocking_floors(
        db, org_id=current_user.organization_id, month_index=month_index
    )


@router.get("/game-plan")
async def game_plan(
    current_user: OperatorUser,
    db: DBSession,
    month_index: int = Query(1, ge=1, le=24),
):
    """FULL-MACHINE priority-ranked action list (every avenue, every engine)."""
    return await compute_game_plan(
        db, org_id=current_user.organization_id, month_index=month_index
    )


@router.get("/ask-operator")
async def ask_operator(
    current_user: OperatorUser,
    db: DBSession,
    month_index: int = Query(1, ge=1, le=24),
):
    """What GM needs from the operator right now — concrete list by priority.

    Includes: pending approvals, open escalations, dormant-avenue
    activations, code-only avenue first-steps, missing credentials,
    budget/authority decisions.
    """
    return await compute_ask_operator(
        db, org_id=current_user.organization_id, month_index=month_index
    )


@router.get("/unlock-plans")
async def unlock_plans(current_user: OperatorUser, db: DBSession):
    """Canonical unlock plans for every LIVE_BUT_DORMANT avenue (and
    PRESENT_IN_CODE_ONLY avenues with unlock plans defined)."""
    return await compute_unlock_plans(db, org_id=current_user.organization_id)


@router.get("/startup-inspection")
async def startup_inspection(
    current_user: OperatorUser,
    db: DBSession,
    month_index: int = Query(1, ge=1, le=24),
):
    """Single-fetch session opener — full-machine state in one call."""
    from apps.api.services.gm_startup import run_revenue_startup_inspection
    return await run_revenue_startup_inspection(
        db, org_id=current_user.organization_id, month_index=month_index
    )
