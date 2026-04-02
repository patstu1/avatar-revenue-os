"""Campaign Constructor API."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.campaigns import CampaignOut, CampaignVariantOut, CampaignBlockerOut, RecomputeSummaryOut
from apps.api.services import campaign_service as svc
from packages.db.models.core import Brand

router = APIRouter()

async def _rb(brand_id, current_user, db):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Brand not accessible")

@router.get("/{brand_id}/campaigns", response_model=list[CampaignOut])
async def list_campaigns(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_campaigns(db, brand_id)

@router.post("/{brand_id}/campaigns/recompute", response_model=RecomputeSummaryOut)
async def recompute(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _rb(brand_id, current_user, db); result = await svc.recompute_campaigns(db, brand_id); await db.commit(); return RecomputeSummaryOut(**result)

@router.get("/{brand_id}/campaign-variants", response_model=list[CampaignVariantOut])
async def list_variants(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_campaign_variants(db, brand_id)

@router.get("/{brand_id}/campaign-blockers", response_model=list[CampaignBlockerOut])
async def list_blockers(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_campaign_blockers(db, brand_id)
