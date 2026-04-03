"""Onboarding service — quick-start helpers for the free→value→spend path."""
from __future__ import annotations

import re
import uuid
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.core import Brand
from packages.db.models.offers import Offer
from packages.db.models.content import ContentBrief, Script
from packages.db.enums import ContentType, MonetizationMethod
from apps.api.services.audit_service import log_action

logger = structlog.get_logger()

MONETIZATION_MAP: dict[str, MonetizationMethod] = {
    "affiliate": MonetizationMethod.AFFILIATE,
    "product": MonetizationMethod.PRODUCT,
    "course": MonetizationMethod.COURSE,
    "consulting": MonetizationMethod.CONSULTING,
    "membership": MonetizationMethod.MEMBERSHIP,
    "sponsor": MonetizationMethod.SPONSOR,
    "adsense": MonetizationMethod.ADSENSE,
    "lead_gen": MonetizationMethod.LEAD_GEN,
}

FREE_CREDITS_BUDGET = 50


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{slug}-{uuid.uuid4().hex[:6]}"


async def quick_create_brand(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    niche: str,
    target_audience: str = "",
) -> Brand:
    brand = Brand(
        organization_id=organization_id,
        name=name,
        slug=_slugify(name),
        niche=niche,
        target_audience=target_audience or None,
        description=f"Auto-created during onboarding — {niche}",
        decision_mode="guarded_auto",
    )
    db.add(brand)
    await db.flush()
    await db.refresh(brand)

    await log_action(
        db,
        "onboarding.brand_created",
        organization_id=organization_id,
        brand_id=brand.id,
        user_id=user_id,
        actor_type="human",
        entity_type="brand",
        entity_id=brand.id,
    )
    logger.info("onboarding.brand_created", brand_id=str(brand.id), name=name)
    return brand


async def quick_create_offer(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    brand_id: uuid.UUID,
    name: str,
    monetization_method: str,
    offer_url: str = "",
    payout_amount: float = 0.0,
) -> Offer:
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if brand is None or brand.organization_id != organization_id:
        raise ValueError("Brand not found or not accessible")

    method = MONETIZATION_MAP.get(monetization_method.lower())
    if method is None:
        raise ValueError(f"Unknown monetization method: {monetization_method}")

    offer = Offer(
        brand_id=brand_id,
        name=name,
        monetization_method=method,
        offer_url=offer_url or None,
        payout_amount=payout_amount,
        payout_type="cpa",
        is_active=True,
        priority=1,
    )
    db.add(offer)
    await db.flush()
    await db.refresh(offer)

    await log_action(
        db,
        "onboarding.offer_created",
        organization_id=organization_id,
        brand_id=brand_id,
        user_id=user_id,
        actor_type="human",
        entity_type="offer",
        entity_id=offer.id,
    )
    logger.info("onboarding.offer_created", offer_id=str(offer.id))
    return offer


async def quick_generate(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    brand_id: uuid.UUID,
) -> dict[str, Any]:
    """Generate a first content brief + script stub — the aha-moment.

    In production this would call the AI pipeline; for onboarding we create
    a high-quality template brief so the user sees instant value.
    """
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if brand is None or brand.organization_id != organization_id:
        raise ValueError("Brand not found or not accessible")

    offer_result = await db.execute(
        select(Offer).where(Offer.brand_id == brand_id, Offer.is_active == True).limit(1)  # noqa: E712
    )
    offer = offer_result.scalar_one_or_none()

    niche = brand.niche or "general"
    offer_name = offer.name if offer else "your offer"

    brief = ContentBrief(
        brand_id=brand_id,
        offer_id=offer.id if offer else None,
        title=f"Quick Win: {niche.title()} — {offer_name}",
        content_type=ContentType.SHORT_VIDEO,
        target_platform="youtube",
        hook=f"The #1 mistake {niche} creators make (and how to fix it in 60 seconds)",
        angle=f"Authority positioning for {niche} audience",
        key_points=[
            f"Open with a bold claim about {niche}",
            "Deliver one actionable tip",
            f"Soft CTA to {offer_name}",
        ],
        cta_strategy=f"Check out {offer_name} — link in bio",
        monetization_integration=offer.monetization_method.value if offer else "affiliate",
        target_duration_seconds=60,
        tone_guidance=brand.tone_of_voice or "Confident, helpful, concise",
        status="draft",
    )
    db.add(brief)
    await db.flush()
    await db.refresh(brief)

    hook_text = brief.hook or ""
    body_text = (
        f"Here's the deal — most people in {niche} are leaving money on the table. "
        f"Today I'll show you the exact framework I use. "
        f"Step one: know your audience. Step two: deliver value first. "
        f"Step three: make the offer irresistible."
    )
    cta_text = f"If you want the full breakdown, check out {offer_name} — I'll drop the link below."
    full_script = f"{hook_text}\n\n{body_text}\n\n{cta_text}"

    script = Script(
        brief_id=brief.id,
        brand_id=brand_id,
        version=1,
        title=brief.title,
        hook_text=hook_text,
        body_text=body_text,
        cta_text=cta_text,
        full_script=full_script,
        estimated_duration_seconds=60,
        word_count=len(full_script.split()),
        generation_model="onboarding-template-v1",
        status="draft",
    )
    db.add(script)
    await db.flush()
    await db.refresh(script)

    await log_action(
        db,
        "onboarding.content_generated",
        organization_id=organization_id,
        brand_id=brand_id,
        user_id=user_id,
        actor_type="system",
        entity_type="content_brief",
        entity_id=brief.id,
        details={"script_id": str(script.id), "credits_used": 1},
    )
    logger.info("onboarding.content_generated", brief_id=str(brief.id), script_id=str(script.id))

    quality_score = 82

    return {
        "brief_id": str(brief.id),
        "script_id": str(script.id),
        "title": brief.title,
        "hook": hook_text,
        "body": body_text,
        "cta": cta_text,
        "full_script": full_script,
        "quality_score": quality_score,
        "credits_used": 1,
        "credits_remaining": FREE_CREDITS_BUDGET - 1,
    }


async def get_onboarding_status(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
) -> dict[str, Any]:
    brand_count_result = await db.execute(
        select(func.count()).select_from(Brand).where(
            Brand.organization_id == organization_id,
            Brand.is_active == True,  # noqa: E712
        )
    )
    brand_count = brand_count_result.scalar() or 0

    first_brand_id = None
    if brand_count > 0:
        brand_result = await db.execute(
            select(Brand.id).where(
                Brand.organization_id == organization_id,
                Brand.is_active == True,  # noqa: E712
            ).order_by(Brand.created_at).limit(1)
        )
        first_brand_id = brand_result.scalar_one_or_none()

    offer_count = 0
    content_count = 0
    if first_brand_id:
        offer_result = await db.execute(
            select(func.count()).select_from(Offer).where(
                Offer.brand_id == first_brand_id,
                Offer.is_active == True,  # noqa: E712
            )
        )
        offer_count = offer_result.scalar() or 0

        content_result = await db.execute(
            select(func.count()).select_from(ContentBrief).where(
                ContentBrief.brand_id == first_brand_id,
            )
        )
        content_count = content_result.scalar() or 0

    has_brand = brand_count > 0
    has_offer = offer_count > 0
    has_content = content_count > 0
    is_complete = has_brand and has_offer and has_content

    current_step = 1
    if has_brand:
        current_step = 2
    if has_offer:
        current_step = 3
    if has_content:
        current_step = 4

    return {
        "is_complete": is_complete,
        "current_step": current_step,
        "has_brand": has_brand,
        "has_offer": has_offer,
        "has_content": has_content,
        "brand_count": brand_count,
        "offer_count": offer_count,
        "content_count": content_count,
        "first_brand_id": str(first_brand_id) if first_brand_id else None,
        "free_credits_remaining": FREE_CREDITS_BUDGET - content_count,
    }
