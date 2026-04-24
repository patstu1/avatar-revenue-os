"""Public lead capture API — no auth required. Used by offer landing pages."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, text

from apps.api.deps import DBSession
from packages.db.models.core import Brand
from packages.db.models.expansion_pack2_phase_a import LeadOpportunity

router = APIRouter()


class LeadCaptureRequest(BaseModel):
    offer_slug: str
    brand_slug: str
    name: str
    email: str
    company: str = ""
    message: str = ""
    revenue: str = ""


@router.post("/leads/capture")
async def capture_lead(body: LeadCaptureRequest, request: Request, db: DBSession):
    """Public endpoint: capture an inbound lead from an offer landing page.

    No authentication required — this is hit by the public offer pages.
    Persists the lead into lead_opportunities for the matching brand.
    """
    # Resolve brand
    brand = (await db.execute(
        select(Brand).where(Brand.slug == body.brand_slug, Brand.is_active.is_(True))
    )).scalar_one_or_none()

    if not brand:
        return {"captured": False, "reason": "brand_not_found"}

    # Resolve offer_id from slug match
    offer_id = None
    try:
        from packages.db.models.offers import Offer
        offers = (await db.execute(
            select(Offer).where(Offer.brand_id == brand.id, Offer.is_active.is_(True))
        )).scalars().all()
        # Match by slug-ified name
        for o in offers:
            slug = o.name.lower().replace(" ", "-").replace("_", "-")
            if slug == body.offer_slug or body.offer_slug in slug:
                offer_id = o.id
                break
    except Exception:
        pass

    # Persist lead
    lead = LeadOpportunity(
        brand_id=brand.id,
        lead_source=f"landing_page:{body.offer_slug}",
        message_text=f"Name: {body.name}\nEmail: {body.email}\nCompany: {body.company}\nRevenue: {body.revenue}\n\n{body.message}",
        urgency_score=0.5,
        budget_proxy_score=0.5,
        sophistication_score=0.5,
        offer_fit_score=0.8 if offer_id else 0.5,
        trust_readiness_score=0.7,
        composite_score=0.6,
        qualification_tier="warm",
        recommended_action=f"Follow up with {body.name} at {body.email} about {body.offer_slug}",
        expected_value=0,
        likelihood_to_close=0.3,
        channel_preference="email",
        confidence=0.7,
        explanation=f"Inbound lead from {body.offer_slug} landing page",
        is_active=True,
    )
    db.add(lead)

    # Also log as system event
    try:
        from packages.db.models.system_events import SystemEvent
        db.add(SystemEvent(
            organization_id=brand.organization_id,
            brand_id=brand.id,
            event_type="lead.captured",
            entity_type="lead_opportunity",
            entity_id=lead.id,
            severity="info",
            domain="revenue",
            summary=f"Lead captured: {body.name} ({body.email}) for {body.offer_slug}",
            details_json={
                "name": body.name,
                "email": body.email,
                "company": body.company,
                "offer_slug": body.offer_slug,
                "source_ip": request.client.host if request.client else None,
            },
        ))
    except Exception:
        pass

    # Auto-create a CloserAction for follow-up execution
    try:
        from packages.db.models.expansion_pack2_phase_a import CloserAction
        db.add(CloserAction(
            brand_id=brand.id,
            lead_opportunity_id=lead.id,
            action_type="initial_follow_up",
            priority=1,
            channel="email",
            subject_or_opener=f"Thanks for your interest in {body.offer_slug.replace('-', ' ').title()}",
            timing="1h",
            rationale=f"Auto-generated follow-up for inbound lead {body.name} ({body.email})",
            expected_outcome="Acknowledge inquiry, provide next steps, build rapport",
            is_completed=False,
            is_active=True,
        ))
    except Exception:
        pass

    await db.commit()

    return {
        "captured": True,
        "lead_id": str(lead.id),
        "brand": brand.name,
        "offer_slug": body.offer_slug,
    }
