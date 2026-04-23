"""Account Expansion Advisor — API routes."""
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.schemas.expansion_advisor import ExpansionAdvisoryOut, RecomputeSummaryOut
from apps.api.services import expansion_advisor_service as eas
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, user, db: DBSession) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


@router.get("/{brand_id}/expansion-advisor", response_model=list[ExpansionAdvisoryOut])
async def get_advisories(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await eas.list_advisories(db, brand_id)


@router.post("/{brand_id}/expansion-advisor/recompute", response_model=RecomputeSummaryOut)
async def recompute_advisory(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await eas.recompute_advisory(db, brand_id)
