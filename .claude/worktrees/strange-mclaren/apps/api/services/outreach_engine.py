"""Outreach Engine — drafts, queues, and sequences outreach for sponsors and service leads.

This is the bridge between "opportunity identified" and "money arrives."
The machine drafts the email, generates the assets, queues the send,
schedules follow-ups, and tracks responses.

Actual email sending is approval-gated by default (operator reviews before send).
Can be set to autonomous for known-good templates + high-confidence targets.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_action, emit_event
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.offers import SponsorOpportunity, SponsorProfile
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.saas_metrics import HighTicketDeal

logger = structlog.get_logger()


async def draft_sponsor_outreach(
    db: AsyncSession, brand_id: uuid.UUID, sponsor_id: uuid.UUID,
) -> dict:
    """Draft a complete sponsor outreach email ready to send."""
    sponsor = (await db.execute(select(SponsorProfile).where(SponsorProfile.id == sponsor_id))).scalar_one_or_none()
    if not sponsor:
        return {"error": "Sponsor not found"}

    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()

    # Gather performance data for the pitch
    total_followers = (await db.execute(
        select(func.coalesce(func.sum(CreatorAccount.follower_count), 0))
        .where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalar() or 0

    top_content = (await db.execute(
        select(ContentItem.title, PerformanceMetric.impressions)
        .outerjoin(PerformanceMetric, PerformanceMetric.content_item_id == ContentItem.id)
        .where(ContentItem.brand_id == brand_id)
        .order_by(PerformanceMetric.impressions.desc().nullslast()).limit(3)
    )).all()

    avg_engagement = (await db.execute(
        select(func.avg(PerformanceMetric.engagement_rate))
        .where(PerformanceMetric.brand_id == brand_id)
    )).scalar() or 0

    brand_name = brand.name if brand else "Our Brand"
    niche = brand.niche if brand else "content creation"
    contact = sponsor.contact_email or "the sponsor"
    industry = sponsor.industry or "your industry"

    # Draft the email
    subject = f"Partnership Opportunity: {brand_name} × {sponsor.sponsor_name}"

    body = f"""Hi {sponsor.sponsor_name} team,

I'm reaching out from {brand_name} — we create {niche} content across multiple platforms with a combined audience of {total_followers:,}+ followers.

We've been following {sponsor.sponsor_name}'s work in {industry} and believe there's a strong alignment between our audience and your brand.

Here's what we bring to a partnership:
• {total_followers:,}+ total audience across active platforms
• {avg_engagement:.1%} average engagement rate
• Proven content performance in the {niche} space"""

    if top_content:
        body += "\n\nOur top-performing content:"
        for title, impressions in top_content[:3]:
            if title:
                body += f"\n• {title}" + (f" ({int(impressions):,} views)" if impressions else "")

    suggested_min = int(total_followers * 0.02)
    suggested_max = int(total_followers * 0.05)

    body += f"""

We offer several partnership formats:
• Sponsored video/content integration
• Product reviews and dedicated features
• Multi-content series sponsorship
• Custom campaign packages

Our typical partnership range is ${suggested_min:,}–${suggested_max:,} depending on scope and deliverables.

Would you be open to a brief call this week to explore the fit?

Best regards,
{brand_name}"""

    return {
        "sponsor_id": str(sponsor_id),
        "sponsor_name": sponsor.sponsor_name,
        "contact_email": sponsor.contact_email,
        "subject": subject,
        "body": body,
        "suggested_price_range": f"${suggested_min:,}–${suggested_max:,}",
        "audience_size": total_followers,
        "engagement_rate": round(float(avg_engagement), 4),
        "status": "draft_ready",
    }


async def draft_service_proposal(
    db: AsyncSession, brand_id: uuid.UUID, deal_id: uuid.UUID,
) -> dict:
    """Draft a service/consulting proposal document from deal data."""
    deal = (await db.execute(select(HighTicketDeal).where(HighTicketDeal.id == deal_id))).scalar_one_or_none()
    if not deal:
        return {"error": "Deal not found"}

    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    brand_name = brand.name if brand else "Our Team"

    scope_items = {
        "consulting": ["Strategic consultation sessions", "Market analysis and recommendations",
                        "Implementation roadmap", "Monthly progress reviews"],
        "content": ["Content strategy development", "Content creation and production",
                     "Platform optimization", "Performance reporting"],
        "campaign": ["Campaign strategy and planning", "Creative development",
                      "Multi-platform execution", "Results tracking and optimization"],
    }

    product_type = deal.product_type or "consulting"
    scope = scope_items.get(product_type, scope_items["consulting"])

    proposal = f"""PROPOSAL: {product_type.title()} Services
Prepared for: {deal.customer_name}
Prepared by: {brand_name}
Date: {datetime.now(timezone.utc).strftime('%B %d, %Y')}

{'='*50}

EXECUTIVE SUMMARY

{brand_name} proposes a {product_type} engagement with {deal.customer_name} designed to deliver measurable results aligned with your business objectives.

SCOPE OF WORK

{chr(10).join(f'• {item}' for item in scope)}

INVESTMENT

Total: ${deal.deal_value:,.2f}

Payment Structure:
• 50% upon agreement (${deal.deal_value/2:,.2f})
• 50% upon completion (${deal.deal_value/2:,.2f})

TIMELINE

Estimated duration: 4-8 weeks from kickoff
Kickoff available: Within 1 week of agreement

NEXT STEPS

1. Review this proposal
2. Schedule a brief alignment call
3. Finalize scope and timeline
4. Begin work

We look forward to partnering with {deal.customer_name}.

{brand_name}
"""

    return {
        "deal_id": str(deal_id),
        "customer_name": deal.customer_name,
        "product_type": product_type,
        "deal_value": float(deal.deal_value or 0),
        "proposal_text": proposal,
        "status": "draft_ready",
    }


async def draft_follow_up(
    db: AsyncSession, brand_id: uuid.UUID,
    *, entity_type: str, entity_id: uuid.UUID, sequence_step: int = 1,
) -> dict:
    """Draft a follow-up email for a stalled deal or outreach."""
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    brand_name = brand.name if brand else "Our Team"

    if entity_type == "sponsor_opportunity":
        deal = (await db.execute(select(SponsorOpportunity).where(SponsorOpportunity.id == entity_id))).scalar_one_or_none()
        name = deal.title if deal else "your team"
        context = "our sponsorship discussion"
    elif entity_type == "high_ticket_deal":
        deal = (await db.execute(select(HighTicketDeal).where(HighTicketDeal.id == entity_id))).scalar_one_or_none()
        name = deal.customer_name if deal else "your team"
        context = "the proposal we shared"
    else:
        return {"error": f"Unknown entity_type: {entity_type}"}

    templates = {
        1: f"Hi {name},\n\nJust following up on {context}. I wanted to check if you had any questions or if there's anything I can clarify.\n\nHappy to jump on a quick call at your convenience.\n\nBest,\n{brand_name}",
        2: f"Hi {name},\n\nI wanted to circle back on {context}. I understand things get busy — just want to make sure this is still on your radar.\n\nIf the timing isn't right, I completely understand. Just let me know.\n\nBest,\n{brand_name}",
        3: f"Hi {name},\n\nFinal follow-up on {context}. If this isn't a fit right now, no worries at all. I'll close this thread and we can revisit anytime.\n\nWishing you all the best.\n\n{brand_name}",
    }

    body = templates.get(sequence_step, templates[1])
    subject = f"Following up — {brand_name}" if sequence_step == 1 else f"Quick check-in — {brand_name}"

    return {
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "sequence_step": sequence_step,
        "subject": subject,
        "body": body,
        "status": "draft_ready",
    }


async def generate_sponsor_media_kit(
    db: AsyncSession, brand_id: uuid.UUID,
) -> dict:
    """Generate a media kit / one-pager with brand stats for sponsor pitches."""
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    brand_name = brand.name if brand else "Brand"
    niche = brand.niche if brand else "Content"

    # Aggregate stats
    total_followers = (await db.execute(
        select(func.coalesce(func.sum(CreatorAccount.follower_count), 0))
        .where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalar() or 0

    account_count = (await db.execute(
        select(func.count()).select_from(CreatorAccount)
        .where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalar() or 0

    content_count = (await db.execute(
        select(func.count()).select_from(ContentItem)
        .where(ContentItem.brand_id == brand_id, ContentItem.status == "published")
    )).scalar() or 0

    avg_engagement = (await db.execute(
        select(func.avg(PerformanceMetric.engagement_rate)).where(PerformanceMetric.brand_id == brand_id)
    )).scalar() or 0

    total_impressions = (await db.execute(
        select(func.coalesce(func.sum(PerformanceMetric.impressions), 0)).where(PerformanceMetric.brand_id == brand_id)
    )).scalar() or 0

    # Platform breakdown
    platforms = (await db.execute(
        select(CreatorAccount.platform, func.sum(CreatorAccount.follower_count))
        .where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
        .group_by(CreatorAccount.platform)
    )).all()
    platform_breakdown = {
        (p[0].value if hasattr(p[0], 'value') else str(p[0])): int(p[1] or 0)
        for p in platforms
    }

    media_kit = f"""{'='*50}
{brand_name.upper()} — MEDIA KIT
{niche.title()} Content Creator
{'='*50}

AUDIENCE
• Total Reach: {total_followers:,} followers
• Active Platforms: {account_count}
• Published Content: {content_count}+ pieces
• Average Engagement: {float(avg_engagement):.1%}
• Total Impressions: {total_impressions:,}

PLATFORM BREAKDOWN
{chr(10).join(f'• {platform.title()}: {followers:,} followers' for platform, followers in platform_breakdown.items())}

PARTNERSHIP OPTIONS
• Sponsored Content Integration — from ${int(total_followers * 0.01):,}
• Product Review / Feature — from ${int(total_followers * 0.015):,}
• Multi-Content Series — from ${int(total_followers * 0.03):,}
• Custom Campaign Package — custom pricing

CONTENT FORMATS
• Short-form video (TikTok, Reels, Shorts)
• Long-form video (YouTube)
• Written content (Blog, Newsletter)
• Social posts (X, LinkedIn, Threads)

CONTACT
{brand_name}
{"Email: " + (brand.description or "") if brand and brand.description else ""}

{'='*50}
"""

    return {
        "brand_name": brand_name,
        "niche": niche,
        "total_followers": total_followers,
        "platform_breakdown": platform_breakdown,
        "media_kit_text": media_kit,
        "status": "generated",
    }


async def queue_outreach_sequence(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID,
    *, target_type: str, target_id: uuid.UUID,
    draft: dict, auto_send: bool = False,
) -> dict:
    """Queue an outreach email + follow-up sequence.

    If auto_send=False (default), creates approval-gated actions.
    If auto_send=True, would dispatch via SMTP (requires operator permission).
    """
    # Create the initial send action
    action = await emit_action(
        db, org_id=org_id,
        action_type="send_outreach_email",
        title=f"Send: {draft.get('subject', 'Outreach')[:60]}",
        description=f"To: {draft.get('contact_email', 'unknown')}. Review draft and approve send.",
        category="monetization",
        priority="high",
        brand_id=brand_id,
        source_module="outreach_engine",
        action_payload={
            "autonomy_level": "autonomous" if auto_send else "assisted",
            "confidence": 0.8,
            "draft": draft,
            "target_type": target_type,
            "target_id": str(target_id),
        },
    )

    # Schedule follow-ups (7 days and 14 days later)
    for step, days in [(2, 7), (3, 14)]:
        await emit_action(
            db, org_id=org_id,
            action_type="send_follow_up",
            title=f"Follow-up #{step}: {draft.get('subject', 'Outreach')[:40]}",
            description=f"Scheduled follow-up {days} days after initial outreach.",
            category="monetization",
            priority="medium",
            brand_id=brand_id,
            source_module="outreach_engine",
            action_payload={
                "autonomy_level": "assisted",
                "confidence": 0.7,
                "sequence_step": step,
                "days_after_initial": days,
                "target_type": target_type,
                "target_id": str(target_id),
            },
        )

    await emit_event(
        db, domain="monetization", event_type="outreach.sequence_queued",
        summary=f"Outreach sequence queued: {draft.get('subject', 'unknown')[:60]}",
        org_id=org_id, brand_id=brand_id,
        details={"target_type": target_type, "target_id": str(target_id), "steps": 3},
    )

    return {
        "initial_action_id": str(action.id),
        "sequence_steps": 3,
        "auto_send": auto_send,
        "status": "queued" if auto_send else "awaiting_approval",
    }
