"""Causal Attribution API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.causal_attribution import (
    CAConfidenceOut,
    CACreditOut,
    CAHypothesisOut,
    CAReportOut,
    RecomputeSummaryOut,
)
from apps.api.services import causal_attribution_service as svc
from packages.db.models.core import Brand

router = APIRouter()


async def _rb(bid, cu, db):
    b = (await db.execute(select(Brand).where(Brand.id == bid))).scalar_one_or_none()
    if not b or b.organization_id != cu.organization_id:
        raise HTTPException(status_code=403, detail="Brand not accessible")


@router.get("/{brand_id}/causal-attribution", response_model=list[CAReportOut])
async def reports(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_reports(db, brand_id)


@router.post("/{brand_id}/causal-attribution/recompute", response_model=RecomputeSummaryOut)
async def recompute(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _rb(brand_id, current_user, db)
    r = await svc.recompute_attribution(db, brand_id)
    await db.commit()
    return RecomputeSummaryOut(**r)


@router.get("/{brand_id}/causal-attribution/hypotheses", response_model=list[CAHypothesisOut])
async def hypotheses(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_hypotheses(db, brand_id)


@router.get("/{brand_id}/causal-attribution/credits", response_model=list[CACreditOut])
async def credits(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_credits(db, brand_id)


@router.get("/{brand_id}/causal-attribution/confidence", response_model=list[CAConfidenceOut])
async def confidence(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db)
    return await svc.list_confidence(db, brand_id)
