"""Lead Magnet Auto-Generation + Email List Pipeline.

Analyzes top-performing content → generates lead magnets via AI → creates landing pages →
manages email nurture sequences → tracks subscriber revenue.
"""
from __future__ import annotations
import uuid
import logging
from typing import Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models.content import ContentItem
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.landing_pages import LandingPage
from packages.db.models.core import Brand

logger = logging.getLogger(__name__)

LEAD_MAGNET_TYPES = [
    {"type": "checklist", "prompt_suffix": "Create a concise, actionable checklist (10-15 items) that someone can use immediately."},
    {"type": "guide", "prompt_suffix": "Create a short guide (800-1200 words) with practical steps and examples."},
    {"type": "template", "prompt_suffix": "Create a fill-in-the-blank template that saves the reader hours of work."},
    {"type": "cheatsheet", "prompt_suffix": "Create a one-page cheatsheet with the most important facts, formulas, or steps."},
    {"type": "swipe_file", "prompt_suffix": "Create a swipe file of 10-15 proven examples they can model."},
]

EMAIL_NURTURE_SEQUENCE = [
    {"day": 0, "type": "welcome", "subject_template": "Here's your {magnet_type}: {topic}", "purpose": "Deliver the lead magnet + set expectations"},
    {"day": 2, "type": "value", "subject_template": "The #1 mistake people make with {topic}", "purpose": "Deliver pure value, build trust"},
    {"day": 5, "type": "monetize", "subject_template": "The tool that changed everything for me ({topic})", "purpose": "Soft sell of affiliate offer"},
    {"day": 7, "type": "value", "subject_template": "Advanced {topic} strategy most people miss", "purpose": "More value, maintain engagement"},
    {"day": 10, "type": "monetize", "subject_template": "{topic}: Limited time offer inside", "purpose": "Direct offer with urgency"},
    {"day": 14, "type": "value", "subject_template": "Quick {topic} win you can do today", "purpose": "Re-engage, provide quick value"},
]


async def identify_lead_magnet_opportunities(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    """Analyze top-performing content to identify lead magnet topics."""
    top_content = list((await db.execute(
        select(ContentItem).join(PerformanceMetric, PerformanceMetric.content_item_id == ContentItem.id).where(
            ContentItem.brand_id == brand_id,
            ContentItem.status == "published",
        ).order_by(PerformanceMetric.impressions.desc()).limit(10)
    )).scalars().all())

    opportunities = []
    for ci in top_content:
        existing = (await db.execute(
            select(LandingPage).where(
                LandingPage.brand_id == brand_id,
                LandingPage.page_type == "lead_magnet",
                LandingPage.headline.contains(ci.title[:50]),
            )
        )).scalar_one_or_none()
        if existing:
            continue

        magnet_type = LEAD_MAGNET_TYPES[hash(ci.title) % len(LEAD_MAGNET_TYPES)]
        opportunities.append({
            "content_item_id": str(ci.id),
            "topic": ci.title,
            "platform": ci.platform,
            "magnet_type": magnet_type["type"],
            "prompt_suffix": magnet_type["prompt_suffix"],
        })

    return opportunities[:3]


async def generate_lead_magnet(db: AsyncSession, brand_id: uuid.UUID, topic: str, magnet_type: str) -> dict[str, Any]:
    """Generate lead magnet content via AI and create a landing page."""
    from apps.api.services.content_generation_service import _get_ai_client
    from packages.scoring.tiered_routing_engine import route_to_provider

    provider_key = route_to_provider("text", "hero")
    client = await _get_ai_client(provider_key)

    magnet_config = next((m for m in LEAD_MAGNET_TYPES if m["type"] == magnet_type), LEAD_MAGNET_TYPES[0])
    prompt = f"""Create a lead magnet about: {topic}

Type: {magnet_type}
{magnet_config['prompt_suffix']}

Format the output clearly with headers and bullet points.
Make it genuinely valuable — this is what convinces people to join the email list.
"""

    system = "You are an expert content marketer creating high-value lead magnets that convert visitors to email subscribers."
    result = await client.generate(prompt, max_tokens=2048, system=system) if hasattr(client, 'generate') else {"success": False}

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "AI generation failed")}

    magnet_content = result["data"]["text"]

    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()

    page = LandingPage(
        brand_id=brand_id,
        page_type="lead_magnet",
        headline=f"Free {magnet_type.replace('_', ' ').title()}: {topic}",
        subheadline=f"Get instant access to this {magnet_type.replace('_', ' ')} — delivered straight to your inbox.",
        hook_angle="value_first",
        cta_blocks=[{"type": "email_capture", "text": "Get Free Access", "magnet_type": magnet_type}],
        proof_blocks=[{"type": "content_proof", "text": f"Based on our most popular content about {topic}"}],
        tracking_params={"magnet_type": magnet_type, "topic": topic},
        status="draft",
        publish_status="unpublished",
        truth_label="recommendation_only",
    )
    db.add(page)
    await db.flush()

    return {
        "success": True,
        "page_id": str(page.id),
        "magnet_type": magnet_type,
        "topic": topic,
        "content_length": len(magnet_content),
        "headline": page.headline,
    }


def build_nurture_email(sequence_step: dict, topic: str, magnet_type: str, offer_name: str = "") -> dict[str, Any]:
    """Build a single nurture email from the sequence template."""
    subject = sequence_step["subject_template"].format(topic=topic, magnet_type=magnet_type)
    return {
        "day": sequence_step["day"],
        "type": sequence_step["type"],
        "subject": subject,
        "purpose": sequence_step["purpose"],
        "offer_name": offer_name if sequence_step["type"] == "monetize" else "",
    }


def build_full_nurture_sequence(topic: str, magnet_type: str, offer_name: str = "") -> list[dict[str, Any]]:
    """Build a complete email nurture sequence for a lead magnet."""
    return [build_nurture_email(step, topic, magnet_type, offer_name) for step in EMAIL_NURTURE_SEQUENCE]
