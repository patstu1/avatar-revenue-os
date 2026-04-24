"""Trend / Viral workers — 60s light scan + deeper analysis + viral fast-track reactor.

Cross-platform replication: when a trend fires, generate platform-specific content for
EVERY active platform and dispatch via express_publish for fastest time-to-publish.
"""
import logging
import uuid

from celery import shared_task
from sqlalchemy import select

from packages.db.enums import ContentType, Platform
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentBrief
from packages.db.models.core import Brand
from packages.db.session import get_async_session_factory, run_async
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)

VIRAL_SCORE_THRESHOLD = 0.75

# Default trend scan cadence applied to any active brand without an explicit
# brand_guidelines.trend_scan_interval_seconds value. 600s (10 min) is
# conservative for YouTube Data API quotas at the typical fleet size and
# guarantees Discovery (Stage 1 of the autonomous loop) starts producing
# TopicCandidate rows on a fresh install without operator action.
DEFAULT_TREND_SCAN_INTERVAL_SECONDS = 600
MIN_TREND_SCAN_INTERVAL_SECONDS = 60

# ── Platform-specific content format mapping ───────────────────────────────
_PLATFORM_BRIEF_CONFIG: dict[str, dict] = {
    Platform.TIKTOK:    {"content_type": ContentType.SHORT_VIDEO, "duration": 45, "tone": "Energetic, punchy, trend-native"},
    Platform.INSTAGRAM: {"content_type": ContentType.SHORT_VIDEO, "duration": 30, "tone": "Polished, visual-first, aspirational"},
    Platform.YOUTUBE:   {"content_type": ContentType.SHORT_VIDEO, "duration": 58, "tone": "Urgent, informative, timely"},
    Platform.X:         {"content_type": ContentType.TEXT_POST,   "duration": 0,  "tone": "Sharp, witty, conversational"},
    Platform.TWITTER:   {"content_type": ContentType.TEXT_POST,   "duration": 0,  "tone": "Sharp, witty, conversational"},
    Platform.FACEBOOK:  {"content_type": ContentType.STATIC_IMAGE,"duration": 0,  "tone": "Relatable, shareable"},
    Platform.LINKEDIN:  {"content_type": ContentType.TEXT_POST,   "duration": 0,  "tone": "Professional, insightful"},
    Platform.THREADS:   {"content_type": ContentType.TEXT_POST,   "duration": 0,  "tone": "Casual, conversational"},
    Platform.PINTEREST: {"content_type": ContentType.STATIC_IMAGE,"duration": 0,  "tone": "Visual, aspirational"},
    Platform.REDDIT:    {"content_type": ContentType.TEXT_POST,   "duration": 0,  "tone": "Authentic, community-native"},
    Platform.SNAPCHAT:  {"content_type": ContentType.STORY,       "duration": 15, "tone": "Fun, raw, behind-the-scenes"},
}
_DEFAULT_BRIEF_CONFIG = {"content_type": ContentType.SHORT_VIDEO, "duration": 45, "tone": "Urgent, energetic, timely"}


async def _trigger_viral_fast_track(brand_id: uuid.UUID, trend_title: str, niche: str, platform: str = "tiktok"):
    """Cross-platform viral fast-track: generate briefs for EVERY active platform, then express publish.

    For each active CreatorAccount on the brand, creates a platform-adapted brief,
    runs the full generation pipeline, and dispatches via express_publish (highest
    priority queue) instead of the normal publishing queue.

    Uses fastest adequate provider tier for trend-reactive content.
    """
    from apps.api.services.content_generation_service import full_pipeline

    async with get_async_session_factory()() as db:
        # Check if we already acted on this trend
        existing = (await db.execute(
            select(ContentBrief.id).where(
                ContentBrief.brand_id == brand_id,
                ContentBrief.title == trend_title,
            )
        )).scalar_one_or_none()
        if existing:
            return {"skipped": True, "reason": "brief_already_exists"}

        # ── Discover ALL active platforms for this brand ───────────────
        accounts = list((await db.execute(
            select(CreatorAccount).where(
                CreatorAccount.brand_id == brand_id,
                CreatorAccount.is_active.is_(True),
            )
        )).scalars().all())

        if not accounts:
            return {"skipped": True, "reason": "no_active_accounts"}

        # Deduplicate platforms (one brief per platform)
        seen_platforms: set[str] = set()
        platform_accounts: list[tuple[CreatorAccount, str]] = []
        for acct in accounts:
            p = acct.platform.value if hasattr(acct.platform, "value") else str(acct.platform)
            if p not in seen_platforms:
                seen_platforms.add(p)
                platform_accounts.append((acct, p))

        # ── Generate platform-specific briefs + content ────────────────
        generated_items: list[dict] = []
        for acct, plat in platform_accounts:
            try:
                plat_enum = Platform(plat) if plat in [e.value for e in Platform] else None
                config = _PLATFORM_BRIEF_CONFIG.get(plat_enum, _DEFAULT_BRIEF_CONFIG) if plat_enum else _DEFAULT_BRIEF_CONFIG

                brief = ContentBrief(
                    brand_id=brand_id,
                    creator_account_id=acct.id,
                    title=trend_title,
                    content_type=config["content_type"],
                    target_platform=plat,
                    hook=f"Breaking: {trend_title}",
                    angle=f"Viral trend reaction for {plat} — fast, relevant, timely",
                    key_points=[niche, "trending now", plat],
                    cta_strategy="Follow for more — link in bio",
                    monetization_integration="organic",
                    target_duration_seconds=config["duration"],
                    tone_guidance=config["tone"],
                    brief_metadata={
                        "source": "viral_fast_track",
                        "trend_title": trend_title,
                        "niche": niche,
                        "target_platform": plat,
                        "cross_platform": True,
                        "provider_tier_hint": "standard",  # Fastest adequate tier
                    },
                    status="draft",
                )
                db.add(brief)
                await db.flush()

                result = await full_pipeline(db, brief.id)
                await db.commit()

                if result.get("success") and result.get("content_item_id"):
                    generated_items.append({
                        "platform": plat,
                        "content_item_id": result["content_item_id"],
                        "brief_id": str(brief.id),
                        "approved": result.get("approved", False),
                    })
                    logger.info(
                        "VIRAL FAST-TRACK: trend='%s' brand=%s platform=%s approved=%s",
                        trend_title, brand_id, plat, result.get("approved"),
                    )
            except Exception:
                logger.exception("viral fast-track generation failed for platform %s", plat)

        # ── Dispatch ALL generated content via express_publish ─────────
        express_dispatched = 0
        for item in generated_items:
            try:
                from workers.publishing_worker.tasks import express_publish
                express_publish.apply_async(
                    kwargs={
                        "content_item_id": item["content_item_id"],
                        "brand_id": str(brand_id),
                        "reason": f"viral_fast_track:{trend_title}",
                    },
                    priority=9,  # Highest Celery priority
                    queue="publishing",
                )
                express_dispatched += 1
            except Exception:
                logger.exception("express_publish dispatch failed for content %s", item["content_item_id"])

        return {
            "trend_title": trend_title,
            "platforms_targeted": len(platform_accounts),
            "briefs_generated": len(generated_items),
            "express_dispatched": express_dispatched,
            "items": generated_items,
        }


async def _light_scan():
    """Configurable-cadence scan: fetch all signals, compute deltas, dedup, trigger viral reactor.

    Scanning frequency is configurable per brand via brand_guidelines.trend_scan_interval_seconds.
    Brands without a configured interval fall back to DEFAULT_TREND_SCAN_INTERVAL_SECONDS so
    Discovery does not stall on fresh installs.
    """
    from datetime import datetime, timezone

    from apps.api.services.trend_viral_service import light_scan
    from packages.db.models.trend_viral import TrendSourceHealth, ViralOpportunity

    now = datetime.now(timezone.utc)

    async with get_async_session_factory()() as db:
        brands = list((await db.execute(
            select(Brand).where(Brand.is_active.is_(True))
        )).scalars().all())

    c = 0
    used_default_interval = 0
    skipped_not_due = 0
    viral_triggered = 0

    for brand in brands:
        bid = brand.id
        # ── Per-brand configurable scan interval ──────────────────────
        guidelines = brand.brand_guidelines or {}
        interval_seconds = guidelines.get("trend_scan_interval_seconds")
        if interval_seconds is None:
            interval_seconds = DEFAULT_TREND_SCAN_INTERVAL_SECONDS
            used_default_interval += 1

        # Floor protects against misconfiguration (interval=0 → scan every tick).
        interval_seconds = max(MIN_TREND_SCAN_INTERVAL_SECONDS, int(interval_seconds))

        # ── Check if brand is due for a scan ──────────────────────────
        try:
            async with get_async_session_factory()() as db:
                last_health = (await db.execute(
                    select(TrendSourceHealth.created_at).where(
                        TrendSourceHealth.brand_id == bid,
                    ).order_by(TrendSourceHealth.created_at.desc()).limit(1)
                )).scalar_one_or_none()

                if last_health and (now - last_health).total_seconds() < interval_seconds:
                    skipped_not_due += 1
                    continue
        except Exception:
            pass  # If we can't check, scan anyway

        # ── Run the scan ──────────────────────────────────────────────
        try:
            async with get_async_session_factory()() as db:
                await light_scan(db, bid)
                await db.commit()
                c += 1

                # ── Viral reactor: trigger fast-track for hot opportunities ──
                hot_opps = list((await db.execute(
                    select(ViralOpportunity).where(
                        ViralOpportunity.brand_id == bid,
                        ViralOpportunity.composite_score >= VIRAL_SCORE_THRESHOLD,
                        ViralOpportunity.status == "active",
                        ViralOpportunity.is_active.is_(True),
                    ).order_by(ViralOpportunity.composite_score.desc())
                )).scalars().all())

                niche = brand.niche or "general"

                for opp in hot_opps:
                    try:
                        result = await _trigger_viral_fast_track(bid, opp.topic or "Trending Now", niche)
                        if result and not result.get("skipped"):
                            viral_triggered += 1
                            opp.status = "acted_on"
                    except Exception:
                        logger.exception("viral fast-track failed for opp %s", opp.id)
                await db.commit()
        except Exception:
            logger.exception("trend light scan failed %s", bid)

    return {
        "brands_scanned": c,
        "used_default_interval": used_default_interval,
        "skipped_not_due": skipped_not_due,
        "viral_triggered": viral_triggered,
    }


async def _deep_analysis():
    """Threshold-triggered: score, classify, create opportunities."""
    from apps.api.services.trend_viral_service import deep_analysis
    async with get_async_session_factory()() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    c = 0
    for bid in brands:
        try:
            async with get_async_session_factory()() as db:
                await deep_analysis(db, bid); await db.commit(); c += 1
        except Exception:
            logger.exception("trend deep analysis failed %s", bid)
    return c


@shared_task(name="workers.trend_viral_worker.tasks.trend_light_scan", base=TrackedTask)
def trend_light_scan():
    """Base tick for trend scanning. Per-brand frequency is configurable via brand_guidelines.trend_scan_interval_seconds.

    Brands without a configured interval fall back to DEFAULT_TREND_SCAN_INTERVAL_SECONDS
    (currently 600s). To disable scanning for a specific brand, set the value to a very
    high number or pause the brand entirely.
    """
    result = run_async(_light_scan())
    return {"status": "completed", **result}


@shared_task(name="workers.trend_viral_worker.tasks.trend_deep_analysis", base=TrackedTask)
def trend_deep_analysis():
    """Runs every 5 minutes — full scoring + opportunity creation."""
    return {"status": "completed", "brands": run_async(_deep_analysis())}
