"""MXP Experiment Decisions — A/B test prioritisation, outcomes, promotion/suppression."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.mxp_experiment_decisions import (
    ExperimentDecisionOut,
    ExperimentOutcomeActionOut,
    ExperimentOutcomeOut,
    OutcomeActionStatusUpdate,
)
from apps.api.services import experiment_decision_service as svc
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get(
    "/{brand_id}/experiment-decisions",
    response_model=list[ExperimentDecisionOut],
)
async def list_decisions(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_experiment_decisions(db, brand_id)


@router.get(
    "/{brand_id}/experiment-outcomes",
    response_model=list[ExperimentOutcomeOut],
)
async def list_outcomes(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_experiment_outcomes(db, brand_id)


@router.get(
    "/{brand_id}/experiment-outcome-actions",
    response_model=list[ExperimentOutcomeActionOut],
)
async def list_outcome_actions(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_experiment_outcome_actions(db, brand_id)


@router.post(
    "/{brand_id}/experiment-decisions/recompute",
    response_model=dict,
)
async def recompute_decisions(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_experiment_decisions(db, brand_id)
    await log_action(
        db,
        "mxp.experiment_decisions_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="experiment_decision",
        details=result,
    )
    return result


@router.post(
    "/{brand_id}/experiment-outcomes/recompute",
    response_model=dict,
)
async def recompute_outcomes_only(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    """Re-evaluate outcomes from current metrics without rebuilding the decision set."""
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_experiment_outcomes_only(db, brand_id)
    await log_action(
        db,
        "mxp.experiment_outcomes_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="experiment_outcome",
        details=result,
    )
    return result


@router.patch(
    "/{brand_id}/experiment-outcome-actions/{action_id}",
    response_model=ExperimentOutcomeActionOut,
)
async def update_outcome_action_status(
    brand_id: uuid.UUID,
    action_id: uuid.UUID,
    body: OutcomeActionStatusUpdate,
    current_user: OperatorUser,
    db: DBSession,
    _rl=Depends(recompute_rate_limit),
):
    """Transition an experiment outcome action (acknowledge, complete, reject)."""
    await _require_brand(brand_id, current_user, db)
    try:
        result = await svc.update_outcome_action_status(
            db, brand_id, action_id, body.execution_status, body.operator_note
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    await log_action(
        db,
        "mxp.outcome_action_status_updated",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="experiment_outcome_action",
        entity_id=action_id,
        details={"new_status": body.execution_status},
    )
    return result
