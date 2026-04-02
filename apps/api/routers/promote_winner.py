"""Promote-Winner API."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.promote_winner import (
    ActiveExperimentOut, PWWinnerOut, PWLoserOut, PromotedRuleOut,
    CreateExperimentIn, AddObservationIn, RecomputeSummaryOut,
)
from apps.api.services import promote_winner_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get("/{brand_id}/experiments", response_model=list[ActiveExperimentOut])
async def list_experiments(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_active_experiments(db, brand_id)


@router.post("/{brand_id}/experiments", response_model=ActiveExperimentOut, status_code=201)
async def create_experiment(brand_id: uuid.UUID, body: CreateExperimentIn, current_user: OperatorUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    exp = await svc.create_experiment(db, brand_id, body.model_dump())
    await db.commit()
    return exp


@router.post("/{brand_id}/experiments/{experiment_id}/observe", status_code=201)
async def add_observation(brand_id: uuid.UUID, experiment_id: uuid.UUID, body: AddObservationIn, current_user: OperatorUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    await svc.add_observation(db, experiment_id, body.variant_id, body.metric_name, body.metric_value, body.content_item_id)
    await db.commit()
    return {"status": "observation_added"}


@router.post("/{brand_id}/experiments/{experiment_id}/evaluate")
async def evaluate_experiment(brand_id: uuid.UUID, experiment_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await svc.evaluate_experiment(db, experiment_id)
    await db.commit()
    return result


@router.get("/{brand_id}/experiment-winners", response_model=list[PWWinnerOut])
async def list_winners(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_winners(db, brand_id)


@router.get("/{brand_id}/experiment-losers", response_model=list[PWLoserOut])
async def list_losers(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_losers(db, brand_id)


@router.get("/{brand_id}/promoted-rules", response_model=list[PromotedRuleOut])
async def list_promoted_rules(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_promoted_rules(db, brand_id)


@router.post("/{brand_id}/experiments/decay-check", response_model=RecomputeSummaryOut)
async def decay_check(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await svc.run_decay_check(db, brand_id)
    await db.commit()
    return RecomputeSummaryOut(rows_processed=result.get("rules_checked", 0), status=result.get("status", "completed"))
