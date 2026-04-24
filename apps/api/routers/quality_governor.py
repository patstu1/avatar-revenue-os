"""Quality Governor API."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.quality_governor import (
    QGBlockOut,
    QGReportOut,
    RecomputeSummaryOut,
)
from apps.api.services import quality_governor_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")


@router.get("/{brand_id}/quality-governor", response_model=list[QGReportOut])
async def list_reports(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_reports(db, brand_id)


@router.post("/{brand_id}/quality-governor/recompute", response_model=RecomputeSummaryOut)
async def recompute(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await svc.recompute_brand_quality(db, brand_id)
    await db.commit()
    return RecomputeSummaryOut(rows_processed=result["rows_processed"], status=result["status"])


@router.post("/{brand_id}/quality-governor/{content_item_id}/score")
async def score_item(brand_id: uuid.UUID, content_item_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    result = await svc.score_content_item(db, brand_id, content_item_id)
    await db.commit()
    return result


@router.get("/{brand_id}/quality-governor/blocks", response_model=list[QGBlockOut])
async def list_blocks(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await svc.list_blocks(db, brand_id)
