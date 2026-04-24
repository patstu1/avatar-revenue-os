"""Opportunity-Cost Ranking API."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.opportunity_cost import OCReportOut, RankedActionOut, RecomputeSummaryOut
from apps.api.services import opportunity_cost_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get("/{brand_id}/opportunity-cost", response_model=list[OCReportOut])
async def list_reports(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_reports(db, brand_id)


@router.post("/{brand_id}/opportunity-cost/recompute", response_model=RecomputeSummaryOut)
async def recompute(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_ranking(db, brand_id)
    await db.commit()
    return RecomputeSummaryOut(rows_processed=result["rows_processed"], status=result["status"])


@router.get("/{brand_id}/opportunity-cost/ranked-actions", response_model=list[RankedActionOut])
async def list_ranked(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_ranked_actions(db, brand_id)
