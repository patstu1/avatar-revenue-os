"""MXP Creative Memory — reusable content pattern atoms."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.mxp_creative_memory import CreativeMemoryAtomOut
from apps.api.services import creative_memory_service as svc
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get(
    "/{brand_id}/creative-memory-atoms",
    response_model=list[CreativeMemoryAtomOut],
)
async def list_atoms(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.get_creative_memory(db, brand_id)


@router.post(
    "/{brand_id}/creative-memory-atoms/recompute",
    response_model=dict,
)
async def recompute_atoms(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_creative_memory(db, brand_id)
    await log_action(
        db,
        "mxp.creative_memory_atoms_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="creative_memory_atom",
        details=result,
    )
    return result
