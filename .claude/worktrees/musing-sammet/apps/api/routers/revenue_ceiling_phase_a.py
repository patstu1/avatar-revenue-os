"""Revenue Ceiling Phase A — offer ladders, owned audience, sequences, funnel.

POST endpoints write; GETs are read-only.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.revenue_ceiling_phase_a import (
    FunnelLeakOut,
    FunnelStageMetricOut,
    MessageSequenceOut,
    OfferLadderOut,
    OwnedAudienceBundleResponse,
)
from apps.api.services import revenue_ceiling_phase_a_service as rca
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, user, db: DBSession) -> Brand:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


@router.get("/{brand_id}/offer-ladders", response_model=list[OfferLadderOut])
async def list_offer_ladders(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rca.get_offer_ladders(db, brand_id)


@router.post("/{brand_id}/offer-ladders/recompute")
async def recompute_offer_ladders(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await rca.recompute_offer_ladders(db, brand_id)
    await log_action(
        db, "revenue_ceiling.offer_ladders_recomputed",
        organization_id=current_user.organization_id, brand_id=brand_id, user_id=current_user.id,
        actor_type="human", entity_type="offer_ladder", details=result,
    )
    return result


@router.get("/{brand_id}/owned-audience", response_model=OwnedAudienceBundleResponse)
async def get_owned_audience(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rca.get_owned_audience_bundle(db, brand_id)


@router.post("/{brand_id}/owned-audience/recompute")
async def recompute_owned_audience(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await rca.recompute_owned_audience(db, brand_id)
    await log_action(
        db, "revenue_ceiling.owned_audience_recomputed",
        organization_id=current_user.organization_id, brand_id=brand_id, user_id=current_user.id,
        actor_type="human", entity_type="owned_audience", details=result,
    )
    return result


@router.get("/{brand_id}/message-sequences", response_model=list[MessageSequenceOut])
async def list_message_sequences(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rca.get_message_sequences(db, brand_id)


@router.post("/{brand_id}/message-sequences/generate")
async def generate_message_sequences(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await rca.generate_message_sequences(db, brand_id)
    await log_action(
        db, "revenue_ceiling.message_sequences_generated",
        organization_id=current_user.organization_id, brand_id=brand_id, user_id=current_user.id,
        actor_type="human", entity_type="message_sequence", details=result,
    )
    return result


@router.get("/{brand_id}/funnel-stage-metrics", response_model=list[FunnelStageMetricOut])
async def list_funnel_stage_metrics(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rca.get_funnel_stage_metrics(db, brand_id)


@router.get("/{brand_id}/funnel-leaks", response_model=list[FunnelLeakOut])
async def list_funnel_leaks(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _require_brand(brand_id, current_user, db)
    return await rca.get_funnel_leaks(db, brand_id)


@router.post("/{brand_id}/funnel-leaks/recompute")
async def recompute_funnel_leaks(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _require_brand(brand_id, current_user, db)
    result = await rca.recompute_funnel_leaks(db, brand_id)
    await log_action(
        db, "revenue_ceiling.funnel_leaks_recomputed",
        organization_id=current_user.organization_id, brand_id=brand_id, user_id=current_user.id,
        actor_type="human", entity_type="funnel_leak", details=result,
    )
    return result
