"""Onboarding service — quick-start helpers for the free→value→spend path."""
from __future__ import annotations

import re
import uuid
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.audit_service import log_action
from packages.db.enums import ContentType, MonetizationMethod
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentBrief, Script
from packages.db.models.core import Brand
from packages.db.models.offers import Offer

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

# Default brand_guidelines applied to every new brand. Anything the operator
# overrides via the dashboard is merged on top of these defaults.
DEFAULT_BRAND_GUIDELINES: dict[str, Any] = {
    # Trend Discovery cadence — fed to workers.trend_viral_worker._light_scan.
    # Without this, a fresh install never produces TopicCandidate rows and the
    # autonomous loop has no fuel.
    "trend_scan_interval_seconds": 600,
}


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
        brand_guidelines=dict(DEFAULT_BRAND_GUIDELINES),
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
    """Return system state for post-login routing.

    Three possible states:
    - "empty"   → nothing configured, show Control Plane Setup
    - "partial" → some things configured, show Setup Checklist
    - "ready"   → enough configured, go straight to dashboard
    """
    import os

    # --- Brands ---
    brand_count_result = await db.execute(
        select(func.count()).select_from(Brand).where(
            Brand.organization_id == organization_id,
            Brand.is_active == True,  # noqa: E712
        )
    )
    brand_count = brand_count_result.scalar() or 0

    # --- Creator Accounts, Offers, Content, Buffer Profiles (via brand_id join) ---
    account_count = 0
    offer_count = 0
    content_count = 0
    buffer_profile_count = 0

    if brand_count > 0:
        brand_ids_result = await db.execute(
            select(Brand.id).where(
                Brand.organization_id == organization_id,
                Brand.is_active == True,  # noqa: E712
            )
        )
        brand_ids = [r[0] for r in brand_ids_result.fetchall()]

        account_count_result = await db.execute(
            select(func.count()).select_from(CreatorAccount).where(
                CreatorAccount.brand_id.in_(brand_ids),
                CreatorAccount.is_active == True,  # noqa: E712
            )
        )
        account_count = account_count_result.scalar() or 0

        offer_result = await db.execute(
            select(func.count()).select_from(Offer).where(
                Offer.brand_id.in_(brand_ids),
                Offer.is_active == True,  # noqa: E712
            )
        )
        offer_count = offer_result.scalar() or 0

        content_result = await db.execute(
            select(func.count()).select_from(ContentBrief).where(
                ContentBrief.brand_id.in_(brand_ids),
            )
        )
        content_count = content_result.scalar() or 0

        # Canonical "publishing connected" check: mapped Buffer profiles
        from packages.db.models.buffer_distribution import BufferProfile
        bp_result = await db.execute(
            select(func.count()).select_from(BufferProfile).where(
                BufferProfile.brand_id.in_(brand_ids),
                BufferProfile.is_active == True,  # noqa: E712
            )
        )
        buffer_profile_count = bp_result.scalar() or 0

    # --- Integrations / Provider keys configured ---
    from apps.api.services import secrets_service
    db_keys = await secrets_service.get_all_keys(db, organization_id)
    providers_from_db = len([k for k, v in db_keys.items() if v])

    # Check critical env vars as fallback
    critical_env_keys = [
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_AI_API_KEY",
        "ELEVENLABS_API_KEY", "HEYGEN_API_KEY", "BUFFER_API_KEY",
        "STRIPE_API_KEY",
    ]
    providers_from_env = len([k for k in critical_env_keys if os.environ.get(k, "")])
    providers_configured = max(providers_from_db, providers_from_env)

    has_brands = brand_count > 0
    # "Accounts/publishing connected" is canonically satisfied by either:
    #   (a) >=1 active creator_accounts row OR
    #   (b) >=1 active buffer_profiles row (Buffer is the primary distributor)
    has_publishing = (account_count > 0) or (buffer_profile_count > 0)
    has_accounts = has_publishing  # legacy compat
    has_offers = offer_count > 0
    has_content = content_count > 0
    has_providers = providers_configured > 0

    # --- Determine system state ---
    # "ready": has at least one provider + one brand = go to dashboard
    # "partial": has some things but missing critical pieces
    # "empty": nothing at all
    if has_providers and has_brands:
        system_state = "ready"
    elif has_providers or has_brands or has_publishing:
        system_state = "partial"
    else:
        system_state = "empty"

    # Build checklist
    total_channels = account_count + buffer_profile_count
    checklist = [
        {"key": "providers", "label": "Connect AI Providers", "done": has_providers, "count": providers_configured, "priority": 1},
        {"key": "brands", "label": "Create Brands / Projects", "done": has_brands, "count": brand_count, "priority": 2},
        {"key": "accounts", "label": "Connect Publishing Channels", "done": has_publishing, "count": total_channels, "priority": 3},
        {"key": "offers", "label": "Add Revenue Offers", "done": has_offers, "count": offer_count, "priority": 4},
        {"key": "content", "label": "Generate Content", "done": has_content, "count": content_count, "priority": 5},
    ]
    completed_steps = len([c for c in checklist if c["done"]])

    # Legacy compat — is_complete means "don't force onboarding"
    # Now: any provider or brand configured = skip forced onboarding
    is_complete = system_state in ("ready", "partial")

    return {
        "is_complete": is_complete,
        "system_state": system_state,
        "checklist": checklist,
        "completed_steps": completed_steps,
        "total_steps": len(checklist),
        "has_providers": has_providers,
        "has_brands": has_brands,
        "has_accounts": has_accounts,
        "has_offers": has_offers,
        "has_content": has_content,
        "providers_configured": providers_configured,
        "brand_count": brand_count,
        "account_count": account_count,
        "buffer_profile_count": buffer_profile_count,
        "publishing_channel_count": total_channels,
        "offer_count": offer_count,
        "content_count": content_count,
    }
