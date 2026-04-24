"""Autonomous Content Ideation Worker.

Scans trend data, combines with pattern memory and niche intelligence,
auto-creates content briefs ready for generation. Zero human input.
"""
import logging
import uuid
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select

from packages.db.enums import ContentType
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentBrief
from packages.db.models.core import Brand
from packages.db.models.pattern_memory import WinningPatternMemory
from packages.db.session import get_async_session_factory, run_async
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)

PLATFORM_CONTENT_TYPES = {
    "youtube": [ContentType.LONG_VIDEO, ContentType.SHORT_VIDEO],
    "tiktok": [ContentType.SHORT_VIDEO],
    "instagram": [ContentType.SHORT_VIDEO, ContentType.CAROUSEL],
    "x": [ContentType.TEXT_POST],
    "linkedin": [ContentType.TEXT_POST, ContentType.CAROUSEL],
}

SHORT_FORM_DURATION = 60
LONG_FORM_DURATION = 600


async def _ideate_for_brand(brand_id: uuid.UUID):
    """Generate content briefs for a single brand from trend data."""
    from packages.clients.trend_data_clients import GoogleTrendsClient, RedditTrendingClient, YouTubeTrendingClient
    from packages.scoring.niche_research_engine import NICHE_DATABASE

    async with get_async_session_factory()() as db:
        brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
        if not brand:
            return {"brand_id": str(brand_id), "briefs_created": 0, "error": "brand not found"}

        accounts = list((await db.execute(
            select(CreatorAccount).where(
                CreatorAccount.brand_id == brand_id,
                CreatorAccount.is_active.is_(True),
            )
        )).scalars().all())

        if not accounts:
            return {"brand_id": str(brand_id), "briefs_created": 0, "error": "no active accounts"}

        existing_briefs = list((await db.execute(
            select(ContentBrief.title).where(
                ContentBrief.brand_id == brand_id,
                ContentBrief.status.in_(["draft", "ready", "pending_generation", "generating", "script_generated"]),
            )
        )).scalars().all())
        all_recent_titles = list((await db.execute(
            select(ContentBrief.title).where(
                ContentBrief.status.in_(["draft", "ready", "pending_generation", "generating", "script_generated", "approved", "published"]),
            ).order_by(ContentBrief.created_at.desc()).limit(500)
        )).scalars().all())
        existing_titles = set(t.lower() for t in existing_briefs) | set(t.lower() for t in all_recent_titles)

        pending_count = len(existing_titles)
        if pending_count >= 10:
            return {"brand_id": str(brand_id), "briefs_created": 0, "reason": "queue full (10+ pending briefs)"}

        niche = brand.niche or "general"
        niche_data = next((n for n in NICHE_DATABASE if n["niche"] == niche), None)
        niche_keywords = niche_data["keywords"] if niche_data else [niche]

        top_patterns = list((await db.execute(
            select(WinningPatternMemory).where(
                WinningPatternMemory.brand_id == brand_id,
                WinningPatternMemory.is_active.is_(True),
            ).order_by(WinningPatternMemory.win_score.desc()).limit(5)
        )).scalars().all())

        # Load YouTube API key from encrypted DB for trend fetching
        yt_api_key = ""
        if brand and brand.organization_id:
            try:
                from sqlalchemy.orm import Session as SyncSession

                from packages.clients.credential_loader import load_credential
                from packages.db.session import get_sync_engine
                _eng = get_sync_engine()
                with SyncSession(_eng) as _ss:
                    yt_api_key = load_credential(_ss, brand.organization_id, "gemini_flash") or ""
            except Exception:
                pass

        trend_signals = []
        try:
            yt = YouTubeTrendingClient(api_key=yt_api_key)
            yt_result = await yt.fetch_trending()
            if yt_result.get("success"):
                for item in yt_result["data"]:
                    title_lower = item["title"].lower()
                    if any(kw.lower() in title_lower for kw in niche_keywords):
                        trend_signals.append(item)
        except Exception:
            logger.warning("YouTube trend fetch failed during ideation")

        try:
            gt = GoogleTrendsClient()
            gt_result = await gt.fetch_daily_trends()
            if gt_result.get("success"):
                for item in gt_result["data"]:
                    title_lower = item["title"].lower()
                    if any(kw.lower() in title_lower for kw in niche_keywords):
                        trend_signals.append(item)
        except Exception:
            logger.warning("Google Trends fetch failed during ideation")

        try:
            from packages.scoring.niche_research_engine import get_niche_subreddits
            reddit = RedditTrendingClient()
            subs = get_niche_subreddits(niche)
            rd_result = await reddit.fetch_niche_trends(subs)
            if rd_result.get("success"):
                trend_signals.extend(rd_result["data"][:10])
        except Exception:
            logger.warning("Reddit trend fetch failed during ideation")

        from packages.db.models.offers import Offer
        from packages.scoring.niche_research_engine import NICHE_DATABASE as _ND
        from packages.scoring.revenue_optimization_engine import rank_briefs_by_revenue

        # Select best active offer for this brand to attach to new briefs
        best_offer = (await db.execute(
            select(Offer).where(
                Offer.brand_id == brand_id,
                Offer.is_active.is_(True),
            ).order_by(Offer.payout_amount.desc()).limit(1)
        )).scalar_one_or_none()
        default_offer_id = best_offer.id if best_offer else None

        niche_info = next((n for n in _ND if n["niche"] == niche), None)
        offer_payout = niche_info.get("youtube_cpm_range", (5, 15))[1] if niche_info else 10
        affiliate_density = niche_info.get("affiliate_density", 0.5) if niche_info else 0.5

        brief_candidates = []
        for acct in accounts:
            platform = getattr(acct.platform, 'value', str(acct.platform)) if acct.platform else "youtube"
            content_types = PLATFORM_CONTENT_TYPES.get(platform, [ContentType.SHORT_VIDEO])
            for ct in content_types:
                title = _generate_brief_title(niche_keywords, trend_signals, top_patterns, existing_titles)
                if title and title.lower() not in existing_titles:
                    ct_str = ct.value if hasattr(ct, 'value') else str(ct)
                    brief_candidates.append({
                        "title": title, "content_type": ct_str, "platform": platform,
                        "account_id": acct.id, "ct_enum": ct,
                        "offer_payout": offer_payout if affiliate_density > 0.7 else 0,
                        "historical_cvr": 0.02, "estimated_impressions": 2000,
                        "monetization_density": affiliate_density,
                    })
                    existing_titles.add(title.lower())

        ranked = rank_briefs_by_revenue(brief_candidates, niche=niche)

        briefs_created = 0
        max_briefs = min(5, 10 - pending_count)

        for candidate in ranked:
            if briefs_created >= max_briefs:
                break

            title = candidate["title"]
            ct = candidate["ct_enum"]
            platform = candidate["platform"]
            acct_id = candidate["account_id"]

            is_short = ct in (ContentType.SHORT_VIDEO, ContentType.TEXT_POST, ContentType.CAROUSEL)
            duration = SHORT_FORM_DURATION if is_short else LONG_FORM_DURATION
            winning_hook = top_patterns[0].pattern_name if top_patterns else None

            brief = ContentBrief(
                brand_id=brand_id,
                creator_account_id=acct_id,
                offer_id=default_offer_id,
                title=title,
                content_type=ct,
                target_platform=platform,
                hook=winning_hook,
                angle=f"Data-driven {niche} content from trending signals",
                key_points=[kw for kw in niche_keywords[:3]],
                cta_strategy="Check the link in bio/description",
                monetization_integration="affiliate" if niche_data and niche_data.get("affiliate_density", 0) > 0.7 else "organic",
                target_duration_seconds=duration,
                tone_guidance="Engaging, conversational, value-first",
                seo_keywords=niche_keywords[:5],
                brief_metadata={
                    "source": "autonomous_ideation",
                    "trace_id": uuid.uuid4().hex[:16],
                    "trend_signals_count": len(trend_signals),
                    "niche": niche,
                    "revenue_score": candidate.get("revenue_score", 0),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
                status="draft",
            )
            db.add(brief)
            briefs_created += 1

        await db.commit()
        return {"brand_id": str(brand_id), "briefs_created": briefs_created, "trend_signals": len(trend_signals)}


def _generate_brief_title(keywords: list, trends: list, patterns: list, existing: set) -> str:
    """Generate a unique content brief title from trend data + patterns."""
    if trends:
        for t in trends[:5]:
            title = t.get("title", "")
            if title and title.lower() not in existing:
                return title

    if patterns:
        for p in patterns:
            name = p.pattern_name if hasattr(p, 'pattern_name') else p.get("pattern_name", "")
            if name:
                title = f"Why {name} is changing everything in {keywords[0] if keywords else 'this space'}"
                if title.lower() not in existing:
                    return title

    if keywords:
        import random
        templates = [
            f"The truth about {keywords[0]} that nobody talks about",
            f"How to {keywords[0]} the right way in 2026",
            f"I tried {keywords[0]} for 30 days — here's what happened",
            f"Stop doing {keywords[0]} wrong — do this instead",
            f"{keywords[0].title()} secrets the experts won't tell you",
            f"The #1 mistake people make with {keywords[0]}",
            f"Why most people fail at {keywords[0]} (and how to fix it)",
        ]
        random.shuffle(templates)
        for t in templates:
            if t.lower() not in existing:
                return t

    return ""


async def _run_ideation():
    async with get_async_session_factory()() as db:
        brand_ids = list((await db.execute(
            select(Brand.id).where(Brand.is_active.is_(True))
        )).scalars().all())

    total_briefs = 0
    for bid in brand_ids:
        try:
            result = await _ideate_for_brand(bid)
            total_briefs += result.get("briefs_created", 0)
        except Exception:
            logger.exception("ideation failed for brand %s", bid)

    return {"brands_processed": len(brand_ids), "total_briefs_created": total_briefs}


@shared_task(name="workers.content_ideation_worker.tasks.ideate_content", base=TrackedTask)
def ideate_content():
    return run_async(_run_ideation())
