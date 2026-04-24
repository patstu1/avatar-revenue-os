"""Growth Hub API — audience discovery, sponsor pipeline, service sales, quality loop, platform adaptation, outreach, proposals."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from apps.api.deps import CurrentUser, DBSession, OperatorUser

router = APIRouter()

# ── Outreach + Handling ──
@router.post("/growth/draft-sponsor-outreach")
async def draft_sponsor_outreach(current_user: OperatorUser, db: DBSession,
                                   brand_id: uuid.UUID = Query(...), sponsor_id: uuid.UUID = Query(...)):
    """Draft a complete sponsor outreach email ready to send."""
    from apps.api.services.outreach_engine import draft_sponsor_outreach
    return await draft_sponsor_outreach(db, brand_id, sponsor_id)

@router.post("/growth/draft-service-proposal")
async def draft_proposal(current_user: OperatorUser, db: DBSession,
                          brand_id: uuid.UUID = Query(...), deal_id: uuid.UUID = Query(...)):
    """Draft a service/consulting proposal."""
    from apps.api.services.outreach_engine import draft_service_proposal
    return await draft_service_proposal(db, brand_id, deal_id)

@router.post("/growth/generate-media-kit")
async def generate_media_kit(current_user: OperatorUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Generate a sponsor media kit / one-pager."""
    from apps.api.services.outreach_engine import generate_sponsor_media_kit
    return await generate_sponsor_media_kit(db, brand_id)

@router.post("/growth/queue-outreach-sequence")
async def queue_outreach(current_user: OperatorUser, db: DBSession,
                          brand_id: uuid.UUID = Query(...), sponsor_id: uuid.UUID = Query(...)):
    """Draft outreach + queue full follow-up sequence (approval-gated)."""
    from apps.api.services.outreach_engine import draft_sponsor_outreach, queue_outreach_sequence
    draft = await draft_sponsor_outreach(db, brand_id, sponsor_id)
    if "error" in draft:
        return draft
    result = await queue_outreach_sequence(db, current_user.organization_id, brand_id,
                                            target_type="sponsor_profile", target_id=sponsor_id, draft=draft)
    await db.commit()
    return {**result, "draft": draft}

@router.post("/growth/auto-create-brief")
async def auto_create_brief(current_user: OperatorUser, db: DBSession,
                              brand_id: uuid.UUID = Query(...),
                              decision_class: str = Query("monetize"),
                              objective: str = Query("Auto-generated content opportunity"),
                              target_platform: str = Query(None)):
    """Auto-create a content brief from a revenue opportunity."""
    from apps.api.services.pipeline_closer import auto_create_brief_from_decision
    result = await auto_create_brief_from_decision(db, brand_id, decision_class=decision_class,
                                                     objective=objective, target_platform=target_platform)
    await db.commit()
    return result

# ── Reply Ingestion ──
@router.post("/growth/ingest-reply")
async def ingest_email_reply(
    current_user: OperatorUser, db: DBSession,
    sender_email: str = Query(...), subject: str = Query(""), body: str = Query(""),
    brand_id: uuid.UUID = Query(None),
):
    """Ingest an email reply: classify, match to deal, advance stage, create action."""
    from apps.api.services.reply_ingestion import ingest_reply
    result = await ingest_reply(db, current_user.organization_id,
                                 sender_email=sender_email, subject=subject, body=body,
                                 brand_id=brand_id)
    await db.commit()
    return result


@router.post("/growth/poll-inbox")
async def poll_inbox(current_user: OperatorUser, db: DBSession):
    """Poll IMAP inbox for unread replies. Requires IMAP credentials."""
    from apps.api.services.reply_ingestion import poll_imap_inbox
    return await poll_imap_inbox(db, current_user.organization_id)


@router.post("/growth/classify-reply")
async def classify_only(subject: str = Query(""), body: str = Query("")):
    """Classify a reply without ingesting (for testing)."""
    from apps.api.services.reply_ingestion import classify_reply
    return classify_reply(subject, body)


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

# ── Parallel Content Pipeline ──
@router.post("/growth/generate-batch")
async def generate_batch(current_user: OperatorUser, db: DBSession, brand_id: uuid.UUID = Query(...)):
    """Generate scripts for all draft briefs in parallel (up to 10 concurrent)."""
    from apps.api.services.parallel_pipeline import generate_batch
    result = await generate_batch(db, brand_id)
    await db.commit()
    return result


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
