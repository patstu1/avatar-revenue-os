"""Trend / Viral workers — 60s light scan + deeper analysis + viral fast-track reactor."""
import asyncio, logging, uuid
from celery import shared_task
from sqlalchemy import select
from packages.db.session import async_session_factory
from workers.base_task import TrackedTask
from packages.db.models.core import Brand
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentBrief
from packages.db.enums import ContentType
logger = logging.getLogger(__name__)

VIRAL_SCORE_THRESHOLD = 0.75


async def _trigger_viral_fast_track(brand_id: uuid.UUID, trend_title: str, niche: str, platform: str = "tiktok"):
    """Immediately create a brief + run generation for a high-velocity trend. Target: <15 min to publish."""
    from apps.api.services.content_generation_service import full_pipeline

    async with async_session_factory() as db:
        existing = (await db.execute(
            select(ContentBrief.id).where(
                ContentBrief.brand_id == brand_id,
                ContentBrief.title == trend_title,
            )
        )).scalar_one_or_none()
        if existing:
            return {"skipped": True, "reason": "brief_already_exists"}

        acct = (await db.execute(
            select(CreatorAccount).where(
                CreatorAccount.brand_id == brand_id,
                CreatorAccount.is_active.is_(True),
            ).limit(1)
        )).scalar_one_or_none()

        brief = ContentBrief(
            brand_id=brand_id,
            creator_account_id=acct.id if acct else None,
            title=trend_title,
            content_type=ContentType.SHORT_VIDEO,
            target_platform=platform,
            hook=f"Breaking: {trend_title}",
            angle="Viral trend reaction — fast, relevant, timely",
            key_points=[niche, "trending now"],
            cta_strategy="Follow for more — link in bio",
            monetization_integration="organic",
            target_duration_seconds=45,
            tone_guidance="Urgent, energetic, timely",
            brief_metadata={"source": "viral_fast_track", "trend_title": trend_title, "niche": niche},
            status="draft",
        )
        db.add(brief)
        await db.flush()

        result = await full_pipeline(db, brief.id)
        await db.commit()
        logger.info("VIRAL FAST-TRACK: trend='%s' brand=%s result=%s", trend_title, brand_id, result.get("approved"))
        return result


async def _light_scan():
    """60-second cadence: fetch signals, compute deltas, dedup, trigger viral reactor on high scores."""
    from apps.api.services.trend_viral_service import light_scan
    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    c = 0
    viral_triggered = 0
    for bid in brands:
        try:
            async with async_session_factory() as db:
                await light_scan(db, bid); await db.commit(); c += 1

                from packages.db.models.trend_viral import ViralOpportunity
                hot_opps = list((await db.execute(
                    select(ViralOpportunity).where(
                        ViralOpportunity.brand_id == bid,
                        ViralOpportunity.composite_score >= VIRAL_SCORE_THRESHOLD,
                        ViralOpportunity.status == "active",
                        ViralOpportunity.is_active.is_(True),
                    ).order_by(ViralOpportunity.composite_score.desc()).limit(2)
                )).scalars().all())

                brand = (await db.execute(select(Brand).where(Brand.id == bid))).scalar_one_or_none()
                niche = brand.niche if brand else "general"

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
    return {"brands": c, "viral_triggered": viral_triggered}


async def _deep_analysis():
    """Threshold-triggered: score, classify, create opportunities."""
    from apps.api.services.trend_viral_service import deep_analysis
    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand.id))).scalars().all())
    c = 0
    for bid in brands:
        try:
            async with async_session_factory() as db:
                await deep_analysis(db, bid); await db.commit(); c += 1
        except Exception:
            logger.exception("trend deep analysis failed %s", bid)
    return c


@shared_task(name="workers.trend_viral_worker.tasks.trend_light_scan", base=TrackedTask)
def trend_light_scan():
    """Runs every 60 seconds — lightweight signal fetch + delta + viral reactor."""
    result = asyncio.run(_light_scan())
    return {"status": "completed", **result}


@shared_task(name="workers.trend_viral_worker.tasks.trend_deep_analysis", base=TrackedTask)
def trend_deep_analysis():
    """Runs every 5 minutes — full scoring + opportunity creation."""
    return {"status": "completed", "brands": asyncio.run(_deep_analysis())}
