"""Expansion Pack 2 Phase C — referral, competitive gap, sponsor sales, profit guardrail endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.expansion_pack2_phase_c import (
    ReferralProgramRecommendationOut,
    CompetitiveGapReportOut,
    SponsorTargetOut,
    SponsorOutreachSequenceOut,
    ProfitGuardrailReportOut,
)
from apps.api.services import expansion_pack2_phase_c_service as ep2c
from apps.api.services.audit_service import log_action
from packages.db.models.core import Brand

router = APIRouter()


async def _require_brand(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")


# ---------------------------------------------------------------------------
# Referral Program Recommendations
# ---------------------------------------------------------------------------


@router.get(
    "/{brand_id}/referral-programs",
    response_model=list[ReferralProgramRecommendationOut],
)
async def list_referral_programs(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    await _require_brand(brand_id, current_user, db)
    return await ep2c.get_referral_program_recommendations(db, brand_id)


@router.post(
    "/{brand_id}/referral-programs/recompute",
    response_model=dict,
)
async def recompute_referral_programs(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await ep2c.recompute_referral_program_recommendations(db, brand_id)
    await log_action(
        db,
        "ep2c.referral_programs_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="referral_program_recommendation",
        details=result,
    )
    return result


# ---------------------------------------------------------------------------
# Competitive Gap Reports
# ---------------------------------------------------------------------------


@router.get(
    "/{brand_id}/competitive-gaps",
    response_model=list[CompetitiveGapReportOut],
)
async def list_competitive_gaps(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    await _require_brand(brand_id, current_user, db)
    return await ep2c.get_competitive_gap_reports(db, brand_id)


@router.post(
    "/{brand_id}/competitive-gaps/recompute",
    response_model=dict,
)
async def recompute_competitive_gaps(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await ep2c.recompute_competitive_gap_reports(db, brand_id)
    await log_action(
        db,
        "ep2c.competitive_gaps_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="competitive_gap_report",
        details=result,
    )
    return result


# ---------------------------------------------------------------------------
# Sponsor Targets
# ---------------------------------------------------------------------------


@router.get(
    "/{brand_id}/sponsor-targets",
    response_model=list[SponsorTargetOut],
)
async def list_sponsor_targets(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    await _require_brand(brand_id, current_user, db)
    return await ep2c.get_sponsor_targets(db, brand_id)


@router.post(
    "/{brand_id}/sponsor-targets/recompute",
    response_model=dict,
)
async def recompute_sponsor_targets(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await ep2c.recompute_sponsor_targets(db, brand_id)
    await log_action(
        db,
        "ep2c.sponsor_targets_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="sponsor_target",
        details=result,
    )
    return result


# ---------------------------------------------------------------------------
# Sponsor Outreach Sequences
# ---------------------------------------------------------------------------


@router.get(
    "/{brand_id}/sponsor-outreach",
    response_model=list[SponsorOutreachSequenceOut],
)
async def list_sponsor_outreach(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    await _require_brand(brand_id, current_user, db)
    return await ep2c.get_sponsor_outreach_sequences(db, brand_id)


@router.post(
    "/{brand_id}/sponsor-outreach/recompute",
    response_model=dict,
)
async def recompute_sponsor_outreach(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await ep2c.recompute_sponsor_outreach_sequences(db, brand_id)
    await log_action(
        db,
        "ep2c.sponsor_outreach_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="sponsor_outreach_sequence",
        details=result,
    )
    return result


# ---------------------------------------------------------------------------
# Profit Guardrail Reports
# ---------------------------------------------------------------------------


@router.get(
    "/{brand_id}/profit-guardrails",
    response_model=list[ProfitGuardrailReportOut],
)
async def list_profit_guardrails(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession
):
    await _require_brand(brand_id, current_user, db)
    return await ep2c.get_profit_guardrail_reports(db, brand_id)


@router.post(
    "/{brand_id}/profit-guardrails/recompute",
    response_model=dict,
)
async def recompute_profit_guardrails(
    brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)
):
    await _require_brand(brand_id, current_user, db)
    result = await ep2c.recompute_profit_guardrail_reports(db, brand_id)
    await log_action(
        db,
        "ep2c.profit_guardrails_recomputed",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="profit_guardrail_report",
        details=result,
    )
    return result
