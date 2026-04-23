"""Phase 7: sponsor, comment-cash, knowledge graph, roadmap, capital, cockpit.

POST recompute writes. All GETs are read-only.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.phase7 import (
    CapitalAllocationResponse,
    CommentCashResponse,
    KnowledgeGraphResponse,
    OperatorCockpitResponse,
    RoadmapResponse,
    SponsorOpportunitiesResponse,
)
from apps.api.services import phase7_service as p7
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, user, db: DBSession) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


@router.post("/{brand_id}/phase7/recompute")
async def recompute_phase7(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await p7.recompute_phase7(db, brand_id, user_id=current_user.id)
    await log_action(db, "phase7.recomputed", organization_id=current_user.organization_id, brand_id=brand_id, user_id=current_user.id, actor_type="human", entity_type="phase7", details=result)
    return result


@router.get("/{brand_id}/sponsor-opportunities", response_model=SponsorOpportunitiesResponse)
async def list_sponsor_opportunities(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await p7.get_sponsor_opportunities(db, brand_id)


@router.get("/{brand_id}/comment-cash-signals", response_model=CommentCashResponse)
async def list_comment_cash(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await p7.get_comment_cash_signals(db, brand_id)


@router.get("/{brand_id}/roadmap", response_model=RoadmapResponse)
async def get_roadmap(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await p7.get_roadmap(db, brand_id)


@router.get("/{brand_id}/capital-allocation", response_model=CapitalAllocationResponse)
async def get_capital_allocation(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await p7.get_capital_allocation(db, brand_id)


@router.get("/{brand_id}/knowledge-graph", response_model=KnowledgeGraphResponse)
async def get_knowledge_graph(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await p7.get_knowledge_graph(db, brand_id)


@router.get("/{brand_id}/operator-cockpit", response_model=OperatorCockpitResponse)
async def get_operator_cockpit(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await p7.get_operator_cockpit(db, brand_id)
