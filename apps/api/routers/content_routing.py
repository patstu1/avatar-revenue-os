"""Content Routing API — tiered routing decisions and cost tracking."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.schemas.content_routing import (
    CostReportOut,
    MonthlyProjectionOut,
    RecomputeSummaryOut,
    RouteTaskRequest,
    RouteTaskResponse,
    RoutingDecisionOut,
)
from apps.api.services import content_routing_service as crs
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, user, db: DBSession) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


@router.get("/{brand_id}/content-routing/decisions", response_model=list[RoutingDecisionOut])
async def list_decisions(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await crs.list_routing_decisions(db, brand_id)


@router.post("/{brand_id}/content-routing/route", response_model=RouteTaskResponse)
async def route_task(brand_id: uuid.UUID, body: RouteTaskRequest, current_user: OperatorUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    result = await crs.route_task(
        db, brand_id, body.task_description, body.platform, body.content_type, body.is_promoted, body.campaign_type
    )
    return RouteTaskResponse(**result)


@router.get("/{brand_id}/content-routing/cost-reports", response_model=list[CostReportOut])
async def list_cost_reports(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await crs.get_cost_reports(db, brand_id)


@router.post("/{brand_id}/content-routing/cost-reports/recompute", response_model=RecomputeSummaryOut)
async def recompute_cost_report(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await crs.recompute_cost_report(db, brand_id)


@router.get("/{brand_id}/content-routing/monthly-projection", response_model=MonthlyProjectionOut)
async def monthly_projection(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await crs.get_monthly_projection()
