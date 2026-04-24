"""Revenue Machine API — The capstone operating model."""
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from apps.api.deps import CurrentUser, DBSession
from apps.api.services import revenue_machine_service as rms

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class RecordFeeRequest(BaseModel):
    fee_type: str = Field(..., description="Fee category: content_generation, transaction_processing, etc.")
    transaction_amount: float = Field(..., ge=0, description="Base transaction amount the fee is calculated on")
    plan_tier: Optional[str] = Field(None, description="Override plan tier (auto-detected if omitted)")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/machine/report")
async def get_machine_report(current_user: CurrentUser, db: DBSession):
    """Full Revenue Machine diagnostic report."""
    return await rms.get_revenue_machine_report(db, current_user.organization_id)


@router.get("/machine/readiness")
async def get_readiness(current_user: CurrentUser, db: DBSession):
    """Elite Readiness Scorecard — 7-question diagnostic."""
    return await rms.get_elite_readiness(db, current_user.organization_id)


@router.get("/machine/triggers")
async def get_triggers(
    current_user: CurrentUser,
    db: DBSession,
    current_action: Optional[str] = Query(None),
):
    """Active contextual spend triggers for the current user."""
    return await rms.get_active_spend_triggers(
        db, current_user.organization_id, current_user.id, current_action,
    )


@router.get("/machine/engines")
async def get_engines(current_user: CurrentUser, db: DBSession):
    """Operating model health — 5 engines."""
    return await rms.get_operating_model_health(db, current_user.organization_id)


@router.get("/machine/fees")
async def get_fees(current_user: CurrentUser, db: DBSession):
    """Transaction fee summary and projections."""
    return await rms.get_transaction_fee_summary(db, current_user.organization_id)


@router.get("/machine/premium-outputs")
async def get_premium_outputs(current_user: CurrentUser, db: DBSession):
    """Available premium outputs with plan-aware pricing."""
    return await rms.get_premium_output_catalog(db, current_user.organization_id)


@router.post("/machine/fees")
async def record_fee(
    body: RecordFeeRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Record a platform transaction fee event."""
    plan_tier = body.plan_tier
    if not plan_tier:
        from apps.api.services.revenue_machine_service import _get_plan_tier
        plan_tier = await _get_plan_tier(db, current_user.organization_id)

    return await rms.record_transaction_fee(
        db,
        org_id=current_user.organization_id,
        fee_type=body.fee_type,
        transaction_amount=body.transaction_amount,
        plan_tier=plan_tier,
    )
