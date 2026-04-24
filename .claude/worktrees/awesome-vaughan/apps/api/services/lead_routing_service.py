"""Lead routing service — automatically routes captured leads into outreach.

When a lead is captured via the public offer pages, this service:
1. Evaluates the lead's qualification tier
2. Creates EmailSendRequest records for the appropriate outreach sequence
3. The existing execute_emails beat task (every 5min) picks them up and sends via SMTP

No lead should ever dead-end in the database without an outreach action.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


async def route_lead_to_outreach(
    db: AsyncSession,
    lead,  # LeadOpportunity
    brand,  # Brand
    lead_email: str,
    lead_name: str,
    offer_slug: str,
) -> dict[str, Any]:
    """Route a captured lead into the outreach pipeline based on qualification tier.

    Creates EmailSendRequest records that the existing execute_emails beat task
    will pick up and send via SMTP.

    Returns summary of actions taken.
    """
    from packages.db.models.live_execution import EmailSendRequest
    from apps.api.services.event_bus import emit_event

    tier = lead.qualification_tier or "cold"
    score = lead.composite_score or 0.0
    emails_created = 0

    # ── Determine outreach strategy by tier ──
    if score >= 0.8 or tier == "hot":
        emails_created = await _create_hot_sequence(
            db, brand, lead, lead_email, lead_name, offer_slug,
        )
    elif score >= 0.5 or tier == "warm":
        emails_created = await _create_warm_sequence(
            db, brand, lead, lead_email, lead_name, offer_slug,
        )
    else:
        emails_created = await _create_cold_sequence(
            db, brand, lead, lead_email, lead_name, offer_slug,
        )

    await db.flush()

    # ── Emit event ──
    try:
        await emit_event(
            db, domain="revenue", event_type="lead.outreach_queued",
            summary=f"Lead {lead_name} ({tier}) routed — {emails_created} emails queued",
            org_id=brand.organization_id,
            brand_id=brand.id,
            entity_type="lead_opportunity", entity_id=lead.id,
            details={
                "tier": tier,
                "score": score,
                "emails_queued": emails_created,
                "offer_slug": offer_slug,
                "lead_email": lead_email,
            },
        )
    except Exception:
        pass

    logger.info(
        "lead_routing.completed",
        lead_id=str(lead.id), tier=tier, emails=emails_created,
    )

    return {
        "routed": True,
        "tier": tier,
        "emails_queued": emails_created,
    }


async def _create_hot_sequence(
    db: AsyncSession, brand, lead, email: str, name: str, offer_slug: str,
) -> int:
    """Hot lead (score >= 0.8): Direct pitch immediately + follow-up in 2 days."""
    from packages.db.models.live_execution import EmailSendRequest

    first_name = name.split()[0] if name else "there"

    # ── Immediate pitch ──
    db.add(EmailSendRequest(
        brand_id=brand.id,
        to_email=email,
        subject=f"{first_name}, quick question about your content",
        body_html=_hot_pitch_html(first_name, offer_slug, brand.name),
        body_text=_hot_pitch_text(first_name, offer_slug, brand.name),
        status="queued",
        provider="smtp",
        sequence_step="initial_pitch",
        metadata_json={
            "lead_id": str(lead.id),
            "qualification_tier": "hot",
            "offer_slug": offer_slug,
            "source": "lead_routing",
        },
    ))

    # ── Follow-up in 2 days ──
    send_after = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    db.add(EmailSendRequest(
        brand_id=brand.id,
        to_email=email,
        subject=f"Following up, {first_name}",
        body_html=_followup_html(first_name, "1"),
        body_text=_followup_text(first_name, "1"),
        status="queued",
        provider="smtp",
        sequence_step="followup_1",
        metadata_json={
            "lead_id": str(lead.id),
            "qualification_tier": "hot",
            "offer_slug": offer_slug,
            "source": "lead_routing",
            "send_after": send_after,
        },
    ))

    return 2


async def _create_warm_sequence(
    db: AsyncSession, brand, lead, email: str, name: str, offer_slug: str,
) -> int:
    """Warm lead (score 0.5-0.8): Value-first email + 2 follow-ups."""
    from packages.db.models.live_execution import EmailSendRequest

    first_name = name.split()[0] if name else "there"

    # ── Value-first email ──
    db.add(EmailSendRequest(
        brand_id=brand.id,
        to_email=email,
        subject=f"{first_name}, saw your inquiry about {offer_slug.replace('-', ' ')}",
        body_html=_warm_pitch_html(first_name, offer_slug, brand.name),
        body_text=_warm_pitch_text(first_name, offer_slug, brand.name),
        status="queued",
        provider="smtp",
        sequence_step="initial_value",
        metadata_json={
            "lead_id": str(lead.id),
            "qualification_tier": "warm",
            "offer_slug": offer_slug,
            "source": "lead_routing",
        },
    ))

    # ── Follow-up 1 in 3 days ──
    send_after_1 = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    db.add(EmailSendRequest(
        brand_id=brand.id,
        to_email=email,
        subject=f"Quick follow-up, {first_name}",
        body_html=_followup_html(first_name, "1"),
        body_text=_followup_text(first_name, "1"),
        status="queued",
        provider="smtp",
        sequence_step="followup_1",
        metadata_json={
            "lead_id": str(lead.id),
            "qualification_tier": "warm",
            "offer_slug": offer_slug,
            "source": "lead_routing",
            "send_after": send_after_1,
        },
    ))

    # ── Follow-up 2 in 7 days ──
    send_after_2 = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    db.add(EmailSendRequest(
        brand_id=brand.id,
        to_email=email,
        subject=f"Last note from {brand.name}",
        body_html=_followup_html(first_name, "2"),
        body_text=_followup_text(first_name, "2"),
        status="queued",
        provider="smtp",
        sequence_step="followup_2",
        metadata_json={
            "lead_id": str(lead.id),
            "qualification_tier": "warm",
            "offer_slug": offer_slug,
            "source": "lead_routing",
            "send_after": send_after_2,
        },
    ))

    return 3


async def _create_cold_sequence(
    db: AsyncSession, brand, lead, email: str, name: str, offer_slug: str,
) -> int:
    """Cold lead (score < 0.5): Single nurture email."""
    from packages.db.models.live_execution import EmailSendRequest

    first_name = name.split()[0] if name else "there"

    db.add(EmailSendRequest(
        brand_id=brand.id,
        to_email=email,
        subject=f"Thanks for your interest, {first_name}",
        body_html=_nurture_html(first_name, offer_slug, brand.name),
        body_text=_nurture_text(first_name, offer_slug, brand.name),
        status="queued",
        provider="smtp",
        sequence_step="nurture",
        metadata_json={
            "lead_id": str(lead.id),
            "qualification_tier": "cold",
            "offer_slug": offer_slug,
            "source": "lead_routing",
        },
    ))

    return 1


# ---------------------------------------------------------------------------
# Email templates (simple string interpolation — no LLM latency on public endpoint)
# ---------------------------------------------------------------------------

def _hot_pitch_html(name: str, offer: str, brand: str) -> str:
    return f"""<p>Hey {name},</p>
<p>Thanks for reaching out about {offer.replace('-', ' ')}. We've helped brands just like yours
dramatically improve their content performance.</p>
<p>I'd love to learn more about what you're working on and show you exactly how we'd approach it.</p>
<p>Would a quick 15-minute call this week work?</p>
<p>Best,<br/>{brand} Team</p>"""


def _hot_pitch_text(name: str, offer: str, brand: str) -> str:
    return (
        f"Hey {name},\n\n"
        f"Thanks for reaching out about {offer.replace('-', ' ')}. We've helped brands just like yours "
        f"dramatically improve their content performance.\n\n"
        f"I'd love to learn more about what you're working on and show you exactly how we'd approach it.\n\n"
        f"Would a quick 15-minute call this week work?\n\n"
        f"Best,\n{brand} Team"
    )


def _warm_pitch_html(name: str, offer: str, brand: str) -> str:
    return f"""<p>Hey {name},</p>
<p>We noticed your interest in {offer.replace('-', ' ')} and wanted to share some quick context.</p>
<p>We specialize in high-performance content that actually converts — not just looks good.
Our clients typically see measurable improvements within the first month.</p>
<p>Happy to walk you through some examples if you're interested. Just reply to this email.</p>
<p>Best,<br/>{brand} Team</p>"""


def _warm_pitch_text(name: str, offer: str, brand: str) -> str:
    return (
        f"Hey {name},\n\n"
        f"We noticed your interest in {offer.replace('-', ' ')} and wanted to share some quick context.\n\n"
        f"We specialize in high-performance content that actually converts — not just looks good. "
        f"Our clients typically see measurable improvements within the first month.\n\n"
        f"Happy to walk you through some examples if you're interested. Just reply to this email.\n\n"
        f"Best,\n{brand} Team"
    )


def _followup_html(name: str, step: str) -> str:
    return f"""<p>Hey {name},</p>
<p>Just bumping this to the top of your inbox — wanted to make sure you saw my earlier note.</p>
<p>If timing isn't right, no worries at all. Just let me know either way.</p>
<p>Best</p>"""


def _followup_text(name: str, step: str) -> str:
    return (
        f"Hey {name},\n\n"
        f"Just bumping this to the top of your inbox — wanted to make sure you saw my earlier note.\n\n"
        f"If timing isn't right, no worries at all. Just let me know either way.\n\n"
        f"Best"
    )


def _nurture_html(name: str, offer: str, brand: str) -> str:
    return f"""<p>Hey {name},</p>
<p>Thanks for checking out {offer.replace('-', ' ')}. We appreciate your interest.</p>
<p>If you'd like to learn more about how we help brands create high-converting content,
feel free to reply to this email anytime.</p>
<p>Best,<br/>{brand} Team</p>"""


def _nurture_text(name: str, offer: str, brand: str) -> str:
    return (
        f"Hey {name},\n\n"
        f"Thanks for checking out {offer.replace('-', ' ')}. We appreciate your interest.\n\n"
        f"If you'd like to learn more about how we help brands create high-converting content, "
        f"feel free to reply to this email anytime.\n\n"
        f"Best,\n{brand} Team"
    )
