"""Analytics Ingestion Worker — fetches real performance data from platforms.

Pulls YouTube, TikTok, Instagram metrics and writes to PerformanceMetric.
Pulls trending topics and writes to TopicCandidate for discovery.

When API credentials are not configured, tasks log a warning and return
without error. The system degrades gracefully.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from celery import shared_task

from workers.base_task import TrackedTask
from packages.db.session import get_async_session_factory


def _run(coro):
    return asyncio.run(coro)


@shared_task(name="workers.analytics_ingestion_worker.tasks.ingest_platform_analytics", base=TrackedTask)
def ingest_platform_analytics():
    """Fetch performance metrics from YouTube, TikTok, Instagram for all active accounts."""
    return _run(_do_ingest_platform_analytics())


async def _do_ingest_platform_analytics():
    from sqlalchemy import select
    from packages.db.models.accounts import CreatorAccount
    from packages.db.models.publishing import PerformanceMetric
    from packages.clients.analytics_clients import (
        YouTubeAnalyticsClient, TikTokAnalyticsClient, InstagramAnalyticsClient,
    )

    yt = YouTubeAnalyticsClient()
    tt = TikTokAnalyticsClient()
    ig = InstagramAnalyticsClient()

    factory = get_async_session_factory()
    async with factory() as db:
        accounts = (await db.execute(
            select(CreatorAccount).where(CreatorAccount.is_active.is_(True))
        )).scalars().all()

        ingested = 0
        skipped = 0

        for acct in accounts:
            platform = acct.platform.value if hasattr(acct.platform, 'value') else str(acct.platform)
            ext_id = acct.platform_external_id or acct.platform_username or ""

            if not ext_id:
                skipped += 1
                continue

            try:
                if platform == "youtube" and yt.is_configured():
                    data = await yt.fetch_video_metrics(ext_id, days=7)
                    if data.get("configured") and data.get("metrics"):
                        for m in data["metrics"]:
                            db.add(PerformanceMetric(
                                content_item_id=None,
                                creator_account_id=acct.id,
                                brand_id=acct.brand_id,
                                platform=platform,
                                impressions=m.get("views", 0),
                                views=m.get("views", 0),
                                revenue=m.get("estimatedRevenue", 0),
                                engagement_rate=0,
                            ))
                            ingested += 1

                elif platform == "tiktok" and tt.is_configured():
                    data = await tt.fetch_video_metrics(ext_id, days=7)
                    if data.get("configured") and data.get("metrics"):
                        for m in data["metrics"]:
                            db.add(PerformanceMetric(
                                content_item_id=None,
                                creator_account_id=acct.id,
                                brand_id=acct.brand_id,
                                platform=platform,
                                impressions=m.get("view_count", 0),
                                views=m.get("view_count", 0),
                                engagement_rate=0,
                            ))
                            ingested += 1

                elif platform == "instagram" and ig.is_configured():
                    data = await ig.fetch_media_insights(ext_id)
                    if data.get("configured") and data.get("metrics"):
                        for m in data["metrics"]:
                            db.add(PerformanceMetric(
                                content_item_id=None,
                                creator_account_id=acct.id,
                                brand_id=acct.brand_id,
                                platform=platform,
                                impressions=m.get("like_count", 0) + m.get("comments_count", 0),
                                views=0,
                                engagement_rate=0,
                            ))
                            ingested += 1

                else:
                    skipped += 1

            except Exception as e:
                import structlog
                structlog.get_logger().warning("analytics_ingestion.account_failed",
                                               account_id=str(acct.id), platform=platform, error=str(e))
                skipped += 1

        await db.commit()

    return {
        "accounts_processed": len(accounts),
        "metrics_ingested": ingested,
        "skipped": skipped,
        "youtube_configured": yt.is_configured(),
        "tiktok_configured": tt.is_configured(),
        "instagram_configured": ig.is_configured(),
    }


@shared_task(name="workers.analytics_ingestion_worker.tasks.ingest_trend_signals", base=TrackedTask)
def ingest_trend_signals():
    """Fetch trending topics from Google Trends and YouTube for discovery."""
    return _run(_do_ingest_trend_signals())


async def _do_ingest_trend_signals():
    from packages.db.models.discovery import TopicCandidate, TrendSignal
    from packages.clients.analytics_clients import TrendSignalClient
    from packages.db.enums import SignalStrength

    client = TrendSignalClient()

    if not client.is_configured():
        return {"configured": False, "ingested": 0,
                "message": "SERPAPI_KEY or RAPIDAPI_KEY not set — trend ingestion inactive"}

    factory = get_async_session_factory()
    async with factory() as db:
        ingested = 0

        # Google Trends
        trends = await client.fetch_trending_topics()
        if trends.get("trends"):
            for t in trends["trends"][:30]:
                title = t.get("query") or t.get("title") or str(t)
                if isinstance(title, str) and len(title) > 2:
                    db.add(TrendSignal(
                        keyword=title[:200],
                        source="google_trends",
                        volume=t.get("search_volume", 0),
                        velocity=0.5,
                        strength=SignalStrength.MODERATE,
                    ))
                    ingested += 1

        # YouTube Trending
        yt_trends = await client.fetch_youtube_trending()
        if yt_trends.get("topics"):
            for t in yt_trends["topics"][:20]:
                db.add(TopicCandidate(
                    title=t["title"][:400],
                    source="youtube_trending",
                    relevance_score=min(1.0, t.get("views", 0) / 1_000_000),
                    trend_velocity=0.6,
                ))
                ingested += 1

        await db.commit()

    return {"configured": True, "ingested": ingested}
