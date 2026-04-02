"""Brain Architecture Phase B — decisions, policies, confidence, cost/upside, arbitration APIs."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.brain_phase_b import (
    ArbitrationReportOut,
    BrainDecisionOut,
    ConfidenceReportOut,
    PolicyEvaluationOut,
    RecomputeSummaryOut,
    UpsideCostEstimateOut,
)
from apps.api.services import brain_phase_b_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")


@router.get("/{brand_id}/brain-decisions", response_model=list[BrainDecisionOut])
async def list_brain_decisions(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(100, ge=1, le=500),
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_brain_decisions(db, brand_id, limit=limit)


@router.post("/{brand_id}/brain-decisions/recompute", response_model=RecomputeSummaryOut)
async def recompute_brain_decisions(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.recompute_brain_decisions(db, brand_id)
        return RecomputeSummaryOut(
            status="completed",
            detail=(
                f"Brain decisions — {result.get('decisions_created', 0)} decisions, "
                f"{result.get('policies_created', 0)} policies, "
                f"{result.get('confidence_reports_created', 0)} confidence reports, "
                f"{result.get('estimates_created', 0)} estimates"
            ),
            counts=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{brand_id}/policy-evaluations", response_model=list[PolicyEvaluationOut])
async def list_policy_evaluations(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(100, ge=1, le=500),
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_policy_evaluations(db, brand_id, limit=limit)


@router.get("/{brand_id}/confidence-reports", response_model=list[ConfidenceReportOut])
async def list_confidence_reports(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(100, ge=1, le=500),
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_confidence_reports(db, brand_id, limit=limit)


@router.get("/{brand_id}/upside-cost-estimates", response_model=list[UpsideCostEstimateOut])
async def list_upside_cost_estimates(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(100, ge=1, le=500),
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_upside_cost_estimates(db, brand_id, limit=limit)


@router.get("/{brand_id}/arbitration-reports", response_model=list[ArbitrationReportOut])
async def list_arbitration_reports(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    limit: int = Query(50, ge=1, le=200),
):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_arbitration_reports(db, brand_id, limit=limit)
