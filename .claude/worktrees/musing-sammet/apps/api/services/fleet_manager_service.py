"""Fleet Manager Service — auto-create accounts on expansion, manage fleet lifecycle."""
from __future__ import annotations
import uuid
import logging
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models.accounts import CreatorAccount
from packages.db.models.core import Brand
from packages.db.models.autonomous_farm import AccountWarmupPlan, AccountVoiceProfile
from packages.db.enums import Platform
from packages.scoring.voice_profile_engine import generate_voice_profile
from packages.scoring.warmup_engine import determine_warmup_phase
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

PLATFORM_ENUM_MAP = {
    "youtube": Platform.YOUTUBE, "tiktok": Platform.TIKTOK, "instagram": Platform.INSTAGRAM,
    "x": Platform.X, "twitter": Platform.X, "linkedin": Platform.LINKEDIN,
    "reddit": Platform.REDDIT,
}


async def execute_expansion(
    db: AsyncSession, brand_id: uuid.UUID, platform: str, niche: str, username: str,
) -> dict[str, Any]:
    """Create a new CreatorAccount with voice profile and warmup plan."""
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        return {"success": False, "error": "Brand not found"}

    platform_enum = PLATFORM_ENUM_MAP.get(platform.lower())
    if not platform_enum:
        return {"success": False, "error": f"Unknown platform: {platform}"}

    existing = (await db.execute(
        select(CreatorAccount).where(
            CreatorAccount.brand_id == brand_id,
            CreatorAccount.platform == platform_enum,
            CreatorAccount.platform_username == username,
        )
    )).scalar_one_or_none()
    if existing:
        return {"success": False, "error": f"Account {username} on {platform} already exists"}

    acct = CreatorAccount(
        brand_id=brand_id, platform=platform_enum,
        platform_username=username, niche_focus=niche,
        posting_capacity_per_day=1,
    )
    db.add(acct)
    await db.flush()

    voice = generate_voice_profile(str(acct.id), platform, niche)
    db.add(AccountVoiceProfile(
        account_id=acct.id, brand_id=brand_id,
        style=voice["style"], vocabulary_level=voice["vocabulary_level"],
        emoji_usage=voice["emoji_usage"], preferred_hook_style=voice["preferred_hook_style"],
        cta_style=voice["cta_style"], paragraph_style=voice["paragraph_style"],
        signature_phrases=voice["signature_phrases"], tone_keywords=voice["tone_keywords"],
        avoid_keywords=voice["avoid_keywords"], full_profile=voice,
    ))

    phase = determine_warmup_phase(datetime.now(timezone.utc))
    db.add(AccountWarmupPlan(
        account_id=acct.id, brand_id=brand_id,
        current_phase=phase["phase"], age_days=0,
        max_posts_per_day=phase["max_posts_per_day"],
        monetization_allowed=phase["monetization_allowed"],
    ))

    await db.flush()
    return {
        "success": True,
        "account_id": str(acct.id),
        "platform": platform,
        "username": username,
        "niche": niche,
        "voice_style": voice["style"],
        "warmup_phase": phase["phase"],
    }
