"""MXP Recovery — incident detection and prescribed recovery actions."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.mxp_recovery import RecoveryIncidentOut
from apps.api.services import recovery_service as svc
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")


@router.get(
    "/{brand_id}/recovery-incidents",
    response_model=list[RecoveryIncidentOut],
)
async def list_incidents(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_recovery_incidents(db, brand_id)


@router.post(
    "/{brand_id}/recovery-incidents/recompute",
    response_model=dict,
)
async def recompute_incidents(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_recovery_incidents(db, brand_id)
    await log_action(
        db,
        "mxp.recovery_incidents_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="recovery_incident",
        details=result,
    )
    return result
