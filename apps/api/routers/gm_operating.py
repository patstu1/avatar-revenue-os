"""GM operating-output router (Batch 7A).

Six read-only GET endpoints that surface the doctrine-driven computations
in ``gm_situation`` as JSON. The GM LLM tool layer (Batch 7B, next) will
call these via tool-use; for now they are available to the operator UI
and to manual curl verification.

All endpoints require ``OperatorUser`` auth and are org-scoped against
``current_user.organization_id``. Zero mutations.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Query

from apps.api.deps import DBSession, OperatorUser
from apps.api.services.gm_doctrine import (
    ACTION_CLASSES,
    CANONICAL_DATA_TABLES,
    CANONICAL_EVENT_TYPES,
    FLOOR_MONTH_1_CENTS,
    FLOOR_MONTH_12_CENTS,
    FORBIDDEN_BEHAVIORS,
    GM_REVENUE_DOCTRINE,
    PILLARS,
    PRIORITY_RANK,
    STAGE_MACHINE,
)
from apps.api.services.gm_situation import (
    compute_blocking_floors,
    compute_bottlenecks,
    compute_closest_revenue,
    compute_floor_status,
    compute_game_plan,
    compute_pipeline_state,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/gm", tags=["GM Operating"])


# ─── Doctrine surface (read-only, no org scope required) ──────────────


@router.get("/doctrine")
async def read_doctrine(current_user: OperatorUser):
    """Canonical doctrine exposed as structured JSON.

    The LLM reads ``GM_REVENUE_DOCTRINE`` from its system prompt. This
    endpoint exposes the same constants as machine-readable data so
    clients can cross-check doctrine drift without re-parsing text.
    """
    return {
        "floors": {
            "month_1_cents": FLOOR_MONTH_1_CENTS,
            "month_1_usd": FLOOR_MONTH_1_CENTS / 100.0,
            "month_12_cents": FLOOR_MONTH_12_CENTS,
            "month_12_usd": FLOOR_MONTH_12_CENTS / 100.0,
        },
        "pillars": list(PILLARS),
        "action_classes": list(ACTION_CLASSES),
        "stage_machine": STAGE_MACHINE,
        "priority_rank": list(PRIORITY_RANK),
        "forbidden_behaviors": list(FORBIDDEN_BEHAVIORS),
        "canonical_data_tables": list(CANONICAL_DATA_TABLES),
        "canonical_event_types": list(CANONICAL_EVENT_TYPES),
        "initialization_brief_preview": GM_REVENUE_DOCTRINE[:1000] + " ...",
    }


# ─── Operating outputs ────────────────────────────────────────────────


@router.get("/floor-status")
async def floor_status(
    current_user: OperatorUser,
    db: DBSession,
    month_index: int = Query(1, ge=1, le=24),
):
    """Trailing-30d revenue vs the floor for the given month index.

    Defaults to month 1 ($30k floor). Set ``month_index=12`` for the
    $1M floor. Interpolated log-linearly for months 2-11.
    """
    return await compute_floor_status(
        db, org_id=current_user.organization_id, month_index=month_index
    )


@router.get("/pipeline-state")
async def pipeline_state(current_user: OperatorUser, db: DBSession):
    """Entity counts for each doctrine stage + the worst bottleneck."""
    return await compute_pipeline_state(db, org_id=current_user.organization_id)


@router.get("/bottlenecks")
async def bottlenecks(current_user: OperatorUser, db: DBSession):
    """Ranked list of stuck + overdue stage entities."""
    return await compute_bottlenecks(db, org_id=current_user.organization_id)


@router.get("/closest-revenue")
async def closest_revenue(current_user: OperatorUser, db: DBSession):
    """Entities one action away from money, bucketed by readiness."""
    return await compute_closest_revenue(db, org_id=current_user.organization_id)


@router.get("/blocking-floors")
async def blocking_floors(
    current_user: OperatorUser,
    db: DBSession,
    month_index: int = Query(1, ge=1, le=24),
):
    """What specifically sits between trailing-30d revenue and the floor."""
    return await compute_blocking_floors(
        db, org_id=current_user.organization_id, month_index=month_index
    )


@router.get("/game-plan")
async def game_plan(
    current_user: OperatorUser,
    db: DBSession,
    month_index: int = Query(1, ge=1, le=24),
):
    """Ranked concrete-action list following the doctrine priority engine."""
    return await compute_game_plan(
        db, org_id=current_user.organization_id, month_index=month_index
    )


# ─── Startup inspection (what GM should read on session init) ─────────


@router.get("/startup-inspection")
async def startup_inspection(
    current_user: OperatorUser,
    db: DBSession,
    month_index: int = Query(1, ge=1, le=24),
):
    """Single-fetch of everything GM needs at session open.

    Mirrors ``gm_startup.run_revenue_startup_inspection`` so an operator
    (or the LLM tool layer) can hit one endpoint instead of five.
    """
    from apps.api.services.gm_startup import run_revenue_startup_inspection

    return await run_revenue_startup_inspection(
        db, org_id=current_user.organization_id, month_index=month_index
    )
