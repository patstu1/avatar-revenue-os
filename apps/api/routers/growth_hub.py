"""Growth Hub API — audience discovery, sponsor pipeline, service sales, quality loop, platform adaptation."""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Query
from apps.api.deps import CurrentUser, DBSession, OperatorUser

router = APIRouter()

# ── Audience Growth ──
@router.get("/growth/audience-expansion")
async def get_audience_expansion(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    from apps.api.services.audience_growth_engine import discover_audience_expansion_opportunities
    return await discover_audience_expansion_opportunities(db, brand_id)

@router.post("/growth/audience-actions")
async def surface_audience_actions(current_user: OperatorUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    from apps.api.services.audience_growth_engine import surface_audience_growth_actions
    actions = await surface_audience_growth_actions(db, current_user.organization_id, brand_id)
    await db.commit()
    return {"actions_created": len(actions), "actions": actions}

# ── Sponsor Pipeline ──
@router.get("/growth/sponsor-pipeline")
async def get_sponsor_pipeline(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    from apps.api.services.sponsor_pipeline_service import get_sponsor_pipeline
    return await get_sponsor_pipeline(db, brand_id)

@router.get("/growth/sponsor-fit-scores")
async def get_sponsor_fit(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    from apps.api.services.sponsor_pipeline_service import score_sponsor_fit
    return await score_sponsor_fit(db, brand_id)

@router.get("/growth/sponsor-outreach-brief")
async def get_outreach_brief(current_user: CurrentUser, db: DBSession,
                              brand_id: uuid.UUID = Query(...), sponsor_id: uuid.UUID = Query(...)):
    from apps.api.services.sponsor_pipeline_service import generate_outreach_brief
    return await generate_outreach_brief(db, brand_id, sponsor_id)

@router.post("/growth/sponsor-actions")
async def surface_sponsor_actions(current_user: OperatorUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    from apps.api.services.sponsor_pipeline_service import surface_sponsor_actions
    actions = await surface_sponsor_actions(db, current_user.organization_id, brand_id)
    await db.commit()
    return {"actions_created": len(actions), "actions": actions}

# ── Service Sales ──
@router.get("/growth/service-pipeline")
async def get_service_pipeline(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    from apps.api.services.service_sales_engine import get_service_pipeline
    return await get_service_pipeline(db, brand_id)

@router.get("/growth/service-leads")
async def get_qualified_leads(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    from apps.api.services.service_sales_engine import qualify_leads
    return await qualify_leads(db, brand_id)

@router.post("/growth/service-actions")
async def surface_service_actions(current_user: OperatorUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    from apps.api.services.service_sales_engine import surface_service_actions
    actions = await surface_service_actions(db, current_user.organization_id, brand_id)
    await db.commit()
    return {"actions_created": len(actions), "actions": actions}

# ── Quality Feedback Loop ──
@router.post("/growth/quality-feedback")
async def run_quality_feedback(current_user: OperatorUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    from apps.api.services.quality_feedback_loop import run_quality_feedback
    result = await run_quality_feedback(db, brand_id)
    await db.commit()
    return result

# ── Platform Adaptation ──
@router.get("/growth/platform-traction")
async def get_platform_traction(current_user: CurrentUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    from apps.api.services.platform_adaptation_engine import analyze_platform_traction
    return await analyze_platform_traction(db, brand_id)

@router.post("/growth/platform-adaptation-actions")
async def surface_adaptation_actions(current_user: OperatorUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    from apps.api.services.platform_adaptation_engine import surface_adaptation_actions
    actions = await surface_adaptation_actions(db, current_user.organization_id, brand_id)
    await db.commit()
    return {"actions_created": len(actions), "actions": actions}
