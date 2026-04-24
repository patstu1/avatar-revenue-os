"""Growth Commander: exact portfolio-expansion commands.
POST recompute writes. All GETs are read-only.
"""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.growth_commander import (
    GrowthCommandResponse, GrowthCommandRunResponse, PortfolioAssessmentResponse,
)
from apps.api.services import growth_commander_service as gcs
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, user, db: DBSession) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


@router.post("/{brand_id}/growth-commands/recompute")
async def recompute_growth_commands(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await gcs.recompute_growth_commands(db, brand_id, user_id=current_user.id)
    await log_action(db, "growth_commander.recomputed", organization_id=current_user.organization_id,
                     brand_id=brand_id, user_id=current_user.id, actor_type="human",
                     entity_type="growth_command", details=result)
    return result


@router.get("/{brand_id}/growth-commands", response_model=list[GrowthCommandResponse])
async def list_growth_commands(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gcs.get_growth_commands(db, brand_id)


@router.get("/{brand_id}/growth-command-runs", response_model=list[GrowthCommandRunResponse])
async def list_growth_command_runs(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gcs.list_growth_command_runs(db, brand_id)


@router.get("/{brand_id}/portfolio-assessment", response_model=PortfolioAssessmentResponse)
async def get_portfolio_assessment(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await gcs.get_portfolio_assessment(db, brand_id)
