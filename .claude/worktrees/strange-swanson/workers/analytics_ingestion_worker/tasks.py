"""Analytics Ingestion Worker — fetches real performance data from platforms.

Pulls YouTube, TikTok, Instagram metrics and writes to PerformanceMetric.
Pulls trending topics and writes to TopicCandidate for discovery.

Credentials loaded from encrypted DB via credential_loader, with .env fallback.
When API credentials are not configured, tasks log a warning and return
without error. The system degrades gracefully.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import structlog
from celery import shared_task

from workers.base_task import TrackedTask
from packages.db.session import get_async_session_factory, run_async

logger = structlog.get_logger()


def _run(coro):
    return run_async(coro)


def _load_analytics_credentials(session, org_id: uuid.UUID) -> dict:
    """Load all analytics-related credentials from encrypted DB.

    Uses credential_loader (DB-first, .env fallback) so analytics clients
    don't call os.environ directly.
    """
    if not session or not org_id:
        return {}
    try:
        from packages.clients.credential_loader import load_credential, load_credential_full
        return {
            "youtube_api_key": load_credential(session, org_id, "youtube_analytics"),
            "youtube_oauth_token": (load_credential_full(session, org_id, "youtube_analytics") or {}).get("oauth_token"),
            "tiktok_access_token": load_credential(session, org_id, "tiktok_analytics"),
            "instagram_access_token": load_credential(session, org_id, "instagram_analytics"),
            "serpapi_key": load_credential(session, org_id, "serpapi"),
        }
    except Exception as e:
        logger.warning("analytics_cred_load_failed", error=str(e))
        return {}


def _compute_engagement_rate(views: int, likes: int, comments: int, shares: int) -> float:
    """Compute engagement rate: (likes + comments + shares) / views."""
    if views <= 0:
        return 0.0
    return round((likes + comments + shares) / views, 6)


async def _resolve_content_item_id(
    db, account_id: uuid.UUID, platform_post_id: str | None,
) -> uuid.UUID | None:
    """Map a platform's post/video ID back to our ContentItem via PublishJob.

    Returns the linked content_item_id when we previously published this asset
    through the system. Returns None for content published outside the system,
    or when the platform's ID format differs from what we stored. The caller
    is responsible for the unresolved telemetry.
    """
    if not platform_post_id:
        return None
    from sqlalchemy import select
    from packages.db.models.publishing import PublishJob
    row = (await db.execute(
        select(PublishJob.content_item_id).where(
            PublishJob.creator_account_id == account_id,
            PublishJob.platform_post_id == str(platform_post_id),
        ).limit(1)
    )).scalar_one_or_none()
    return row


@shared_task(name="workers.analytics_ingestion_worker.tasks.ingest_platform_analytics", base=TrackedTask)
def ingest_platform_analytics():
    """Fetch performance metrics from YouTube, TikTok, Instagram for all active accounts."""
    return _run(_do_ingest_platform_analytics())


async def _do_ingest_platform_analytics():
    from sqlalchemy import select
    from sqlalchemy.orm import Session as SyncSession
    from packages.db.models.accounts import CreatorAccount
    from packages.db.models.core import Brand
    from packages.db.models.publishing import PerformanceMetric
    from packages.db.session import get_sync_engine
    from packages.clients.analytics_clients import (
        YouTubeAnalyticsClient, TikTokAnalyticsClient, InstagramAnalyticsClient,
    )

    # Load credentials from encrypted DB (sync, for credential_loader)
    engine = get_sync_engine()
    creds_by_org: dict[uuid.UUID, dict] = {}

    factory = get_async_session_factory()
    async with factory() as db:
        accounts = (await db.execute(
            select(CreatorAccount).where(CreatorAccount.is_active.is_(True))
        )).scalars().all()

        # Pre-load credentials per org
        brand_org_map: dict[uuid.UUID, uuid.UUID] = {}
        brand_ids = {a.brand_id for a in accounts}
        for bid in brand_ids:
            brand = (await db.execute(
                select(Brand).where(Brand.id == bid)
            )).scalar_one_or_none()
            if brand and brand.organization_id:
                brand_org_map[bid] = brand.organization_id

    # Load credentials per org (sync path for credential_loader)
    with SyncSession(engine) as sync_session:
        for org_id in set(brand_org_map.values()):
            if org_id not in creds_by_org:
                creds_by_org[org_id] = _load_analytics_credentials(sync_session, org_id)

    ingested = 0
    skipped = 0
    errors = 0
    linked = 0
    unlinked = 0
    sample_unresolved: list[dict] = []  # First few unresolved IDs per run for diagnostics

    for acct in accounts:
        platform = acct.platform.value if hasattr(acct.platform, "value") else str(acct.platform)
        ext_id = acct.platform_external_id or acct.platform_username or ""

        if not ext_id:
            skipped += 1
            continue

        org_id = brand_org_map.get(acct.brand_id)
        creds = creds_by_org.get(org_id, {}) if org_id else {}

        try:
            if platform == "youtube":
                yt = YouTubeAnalyticsClient(
                    api_key=creds.get("youtube_api_key"),
                    oauth_token=creds.get("youtube_oauth_token"),
                )
                if not yt.is_configured():
                    skipped += 1
                    continue

                data = await yt.fetch_video_metrics(ext_id, days=7)
                if data.get("metrics"):
                    async with factory() as db:
                        for m in data["metrics"]:
                            views = int(m.get("views", 0))
                            likes = int(m.get("likes", 0))
                            comments = int(m.get("comments", 0))
                            shares = int(m.get("shares", 0))
                            revenue = float(m.get("estimatedRevenue", 0))
                            watch_minutes = float(m.get("estimatedMinutesWatched", 0))
                            subs = int(m.get("subscribersGained", 0))

                            # YouTube Analytics returns the video ID under the "video"
                            # column (the dimension we requested in the client).
                            yt_video_id = m.get("video") or m.get("video_id")
                            content_item_id = await _resolve_content_item_id(db, acct.id, yt_video_id)
                            if content_item_id:
                                linked += 1
                            else:
                                unlinked += 1
                                if len(sample_unresolved) < 10 and yt_video_id:
                                    sample_unresolved.append({"platform": "youtube",
                                                              "post_id": yt_video_id,
                                                              "account_id": str(acct.id)})

                            db.add(PerformanceMetric(
                                content_item_id=content_item_id,
                                creator_account_id=acct.id,
                                brand_id=acct.brand_id,
                                platform=platform,
                                impressions=views,
                                views=views,
                                likes=likes,
                                comments=comments,
                                shares=shares,
                                watch_time_seconds=int(watch_minutes * 60),
                                followers_gained=subs,
                                revenue=revenue,
                                rpm=round((revenue / views * 1000), 2) if views > 0 else 0.0,
                                engagement_rate=_compute_engagement_rate(views, likes, comments, shares),
                                raw_data=m,
                            ))
                            ingested += 1
                        await db.commit()

            elif platform == "tiktok":
                tt = TikTokAnalyticsClient(
                    access_token=creds.get("tiktok_access_token"),
                )
                if not tt.is_configured():
                    skipped += 1
                    continue

                data = await tt.fetch_video_metrics(ext_id, days=7)
                if data.get("metrics"):
                    async with factory() as db:
                        for m in data["metrics"]:
                            views = int(m.get("view_count", 0))
                            likes = int(m.get("like_count", 0))
                            comments = int(m.get("comment_count", 0))
                            shares = int(m.get("share_count", 0))

                            tt_video_id = m.get("id") or m.get("video_id") or m.get("item_id")
                            content_item_id = await _resolve_content_item_id(db, acct.id, tt_video_id)
                            if content_item_id:
                                linked += 1
                            else:
                                unlinked += 1
                                if len(sample_unresolved) < 10 and tt_video_id:
                                    sample_unresolved.append({"platform": "tiktok",
                                                              "post_id": tt_video_id,
                                                              "account_id": str(acct.id)})

                            db.add(PerformanceMetric(
                                content_item_id=content_item_id,
                                creator_account_id=acct.id,
                                brand_id=acct.brand_id,
                                platform=platform,
                                impressions=views,
                                views=views,
                                likes=likes,
                                comments=comments,
                                shares=shares,
                                engagement_rate=_compute_engagement_rate(views, likes, comments, shares),
                                raw_data=m,
                            ))
                            ingested += 1
                        await db.commit()

            elif platform == "instagram":
                ig = InstagramAnalyticsClient(
                    access_token=creds.get("instagram_access_token"),
                )
                if not ig.is_configured():
                    skipped += 1
                    continue

                data = await ig.fetch_media_insights(ext_id)
                if data.get("metrics"):
                    async with factory() as db:
                        for m in data["metrics"]:
                            likes = int(m.get("like_count", 0))
                            comments = int(m.get("comments_count", 0))

                            ig_media_id = m.get("id") or m.get("media_id")
                            content_item_id = await _resolve_content_item_id(db, acct.id, ig_media_id)
                            if content_item_id:
                                linked += 1
                            else:
                                unlinked += 1
                                if len(sample_unresolved) < 10 and ig_media_id:
                                    sample_unresolved.append({"platform": "instagram",
                                                              "post_id": ig_media_id,
                                                              "account_id": str(acct.id)})

                            db.add(PerformanceMetric(
                                content_item_id=content_item_id,
                                creator_account_id=acct.id,
                                brand_id=acct.brand_id,
                                platform=platform,
                                impressions=likes + comments,
                                likes=likes,
                                comments=comments,
                                engagement_rate=_compute_engagement_rate(
                                    likes + comments, likes, comments, 0
                                ),
                                raw_data=m,
                            ))
                            ingested += 1
                        await db.commit()

            else:
                skipped += 1

        except Exception as e:
            logger.warning(
                "analytics_ingestion.account_failed",
                account_id=str(acct.id), platform=platform, error=str(e),
            )
            errors += 1

    if unlinked > 0 or linked > 0:
        logger.info(
            "analytics_ingestion.linkage_summary",
            metrics_ingested=ingested,
            content_linked=linked,
            content_unlinked=unlinked,
            link_rate=round(linked / max(linked + unlinked, 1), 3),
            sample_unresolved=sample_unresolved,
        )

    return {
        "accounts_processed": len(accounts),
        "metrics_ingested": ingested,
        "content_linked": linked,
        "content_unlinked": unlinked,
        "skipped": skipped,
        "errors": errors,
    }


@shared_task(name="workers.analytics_ingestion_worker.tasks.ingest_trend_signals", base=TrackedTask)
def ingest_trend_signals():
    """Fetch trending topics from Google Trends and YouTube for discovery."""
    return _run(_do_ingest_trend_signals())


async def _do_ingest_trend_signals():
    from sqlalchemy import select
    from sqlalchemy.orm import Session as SyncSession
    from packages.db.models.discovery import TopicCandidate, TrendSignal
    from packages.db.models.core import Brand
    from packages.db.enums import SignalStrength
    from packages.db.session import get_sync_engine
    from packages.clients.analytics_clients import TrendSignalClient

    # Load credentials from first available org
    engine = get_sync_engine()
    serp_key = None
    yt_key = None

    factory = get_async_session_factory()
    async with factory() as db:
        brand = (await db.execute(
            select(Brand).where(Brand.is_active.is_(True)).limit(1)
        )).scalar_one_or_none()
        org_id = brand.organization_id if brand else None

    if org_id:
        with SyncSession(engine) as sync_session:
            creds = _load_analytics_credentials(sync_session, org_id)
            serp_key = creds.get("serpapi_key")
            yt_key = creds.get("youtube_api_key")

    client = TrendSignalClient(serp_key=serp_key)

    if not client.is_configured():
        return {
            "configured": False, "ingested": 0,
            "message": "SerpAPI key not configured - add in Settings > Integrations",
        }

    factory = get_async_session_factory()
    async with factory() as db:
        ingested = 0

        # Google Trends
        trends = await client.fetch_trending_topics()
        if trends.get("trends"):
            for t in trends["trends"][:30]:
                title = t.get("query") or t.get("title", "")
                if not title:
                    continue
                signal = TrendSignal(
                    source="google_trends",
                    signal_type="trending_topic",
                    title=title,
                    strength=SignalStrength.STRONG if t.get("traffic", 0) > 500000 else SignalStrength.MODERATE,
                    raw_data=t,
                )
                db.add(signal)
                ingested += 1

        # YouTube Trending
        yt_trends = await client.fetch_youtube_trending(youtube_api_key=yt_key)
        if yt_trends.get("videos"):
            for v in yt_trends["videos"][:20]:
                title = v.get("title", "")
                if not title:
                    continue
                signal = TrendSignal(
                    source="youtube_trending",
                    signal_type="trending_video",
                    title=title,
                    strength=SignalStrength.STRONG if v.get("views", 0) > 1_000_000 else SignalStrength.MODERATE,
                    raw_data=v,
                )
                db.add(signal)
                ingested += 1

        await db.commit()

    return {"configured": True, "ingested": ingested}


# ---------------------------------------------------------------------------
# Per-item metrics ingest (event-driven, triggered by publish success)
# ---------------------------------------------------------------------------

@shared_task(
    name="workers.analytics_ingestion_worker.tasks.ingest_metrics_for_content_item",
    base=TrackedTask,
    max_retries=3,
    default_retry_delay=900,  # 15-min backoff if platform has no data yet
)
def ingest_metrics_for_content_item(content_item_id: str, account_id: str):
    """Fetch metrics for a single just-published content item.

    Called with a 5-minute delay after publish success so the platform's
    API has time to start counting. If the platform returns no data, retries
    with a 15-minute backoff (up to 3 retries) before giving up — the 6-hour
    sweep will catch it eventually.

    After writing PerformanceMetric, chains to the causal attribution task
    to close the learning loop without waiting for the next 6-hour cycle.
    """
    return _run(_do_ingest_single_item(content_item_id, account_id))


async def _do_ingest_single_item(content_item_id_str: str, account_id_str: str):
    from sqlalchemy import select
    from packages.db.models.accounts import CreatorAccount
    from packages.db.models.content import ContentItem
    from packages.db.models.publishing import PublishJob, PerformanceMetric
    from packages.db.models.core import Brand
    from packages.db.session import get_sync_engine
    from sqlalchemy.orm import Session as SyncSession
    from packages.clients.analytics_clients import (
        YouTubeAnalyticsClient, TikTokAnalyticsClient, InstagramAnalyticsClient,
    )

    content_item_id = uuid.UUID(content_item_id_str)
    account_id = uuid.UUID(account_id_str)
    factory = get_async_session_factory()

    async with factory() as db:
        acct = (await db.execute(
            select(CreatorAccount).where(CreatorAccount.id == account_id)
        )).scalar_one_or_none()
        if not acct:
            return {"skipped": True, "reason": "account_not_found"}

        job = (await db.execute(
            select(PublishJob).where(
                PublishJob.content_item_id == content_item_id,
            ).order_by(PublishJob.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        platform_post_id = job.platform_post_id if job else None

        if not platform_post_id:
            return {"skipped": True, "reason": "no_platform_post_id"}

        platform = acct.platform.value if hasattr(acct.platform, "value") else str(acct.platform)

        # Load credentials
        org_id = None
        brand = (await db.execute(select(Brand).where(Brand.id == acct.brand_id))).scalar_one_or_none()
        if brand:
            org_id = brand.organization_id

    creds = {}
    if org_id:
        engine = get_sync_engine()
        with SyncSession(engine) as sync_session:
            creds = _load_analytics_credentials(sync_session, org_id)

    views = likes = comments = shares = 0
    revenue = 0.0
    got_data = False

    try:
        if platform == "youtube":
            yt = YouTubeAnalyticsClient(
                api_key=creds.get("youtube_api_key"),
                oauth_token=creds.get("youtube_oauth_token"),
            )
            if yt.is_configured():
                data = await yt.fetch_video_metrics(platform_post_id, days=1)
                for m in data.get("metrics", []):
                    vid = m.get("video") or m.get("video_id") or ""
                    if str(vid) == str(platform_post_id):
                        views = int(m.get("views", 0))
                        likes = int(m.get("likes", 0))
                        comments = int(m.get("comments", 0))
                        shares = int(m.get("shares", 0))
                        revenue = float(m.get("estimatedRevenue", 0))
                        got_data = views > 0
                        break

        elif platform == "tiktok":
            tt = TikTokAnalyticsClient(access_token=creds.get("tiktok_access_token"))
            if tt.is_configured():
                data = await tt.fetch_video_metrics("", days=1)
                for m in data.get("metrics", []):
                    vid = m.get("id") or m.get("video_id") or ""
                    if str(vid) == str(platform_post_id):
                        views = int(m.get("view_count", 0))
                        likes = int(m.get("like_count", 0))
                        comments = int(m.get("comment_count", 0))
                        shares = int(m.get("share_count", 0))
                        got_data = views > 0
                        break

        elif platform == "instagram":
            ig = InstagramAnalyticsClient(access_token=creds.get("instagram_access_token"))
            if ig.is_configured():
                data = await ig.fetch_media_insights(platform_post_id)
                for m in data.get("metrics", []):
                    likes = int(m.get("like_count", 0))
                    comments = int(m.get("comments_count", 0))
                    got_data = likes + comments > 0
                    break

    except Exception as e:
        logger.warning("single_item_ingest.fetch_failed",
                       content_item_id=content_item_id_str, platform=platform, error=str(e))
        return {"ingested": False, "error": str(e)[:200]}

    if not got_data:
        return {"ingested": False, "reason": "no_data_yet"}

    async with factory() as db:
        db.add(PerformanceMetric(
            content_item_id=content_item_id,
            creator_account_id=account_id,
            brand_id=acct.brand_id,
            platform=platform,
            impressions=views,
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
            revenue=revenue,
            engagement_rate=_compute_engagement_rate(views, likes, comments, shares),
        ))
        await db.commit()

    # Chain: trigger per-item attribution
    from workers.causal_attribution_worker.tasks import attribute_revenue_for_content_item
    attribute_revenue_for_content_item.apply_async(
        args=[content_item_id_str],
        countdown=60,
        queue="default",
    )

    return {"ingested": True, "platform": platform, "views": views, "revenue": revenue}
