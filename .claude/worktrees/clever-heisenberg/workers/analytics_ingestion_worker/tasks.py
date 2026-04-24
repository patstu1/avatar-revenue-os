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
from packages.db.session import get_async_session_factory

logger = structlog.get_logger()


def _run(coro):
    return asyncio.run(coro)


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

    # --- Pre-load published post mapping: platform_post_id → content_item_id ---
    # This lets us attribute platform metrics back to the exact content item.
    post_id_to_content: dict[str, uuid.UUID] = {}
    async with factory() as db:
        from packages.db.models.publishing import PublishJob
        from packages.db.enums import JobStatus
        published_jobs = (await db.execute(
            select(PublishJob).where(
                PublishJob.status == JobStatus.COMPLETED,
                PublishJob.platform_post_id.isnot(None),
            )
        )).scalars().all()
        for pj in published_jobs:
            post_id_to_content[pj.platform_post_id] = pj.content_item_id

    ingested = 0
    skipped = 0
    errors = 0
    content_linked = 0

    def _resolve_content_item_id(metric_data: dict, platform_name: str) -> uuid.UUID | None:
        """Match a platform metric row back to a content_item via PublishJob.platform_post_id."""
        # YouTube: video column in analytics response
        video_id = metric_data.get("video") or metric_data.get("video_id") or metric_data.get("id")
        if video_id and str(video_id) in post_id_to_content:
            return post_id_to_content[str(video_id)]
        return None

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
                            cid = _resolve_content_item_id(m, platform)
                            if cid:
                                content_linked += 1

                            db.add(PerformanceMetric(
                                content_item_id=cid,
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
                            cid = _resolve_content_item_id(m, platform)
                            if cid:
                                content_linked += 1

                            db.add(PerformanceMetric(
                                content_item_id=cid,
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
                            cid = _resolve_content_item_id(m, platform)
                            if cid:
                                content_linked += 1

                            db.add(PerformanceMetric(
                                content_item_id=cid,
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

    logger.info("analytics_ingestion.complete",
                accounts=len(accounts), ingested=ingested,
                content_linked=content_linked, skipped=skipped, errors=errors)
    return {
        "accounts_processed": len(accounts),
        "metrics_ingested": ingested,
        "content_items_linked": content_linked,
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


# ── Affiliate Commission Sync ────────────────────────────────────────

@shared_task(name="workers.analytics_ingestion_worker.tasks.sync_affiliate_commissions", base=TrackedTask)
def sync_affiliate_commissions():
    """Fetch commission data from Amazon Associates and Impact, persist to DB."""
    return _run(_do_sync_affiliate_commissions())


async def _do_sync_affiliate_commissions():
    from sqlalchemy import select
    from sqlalchemy.orm import Session as SyncSession
    from packages.db.models.core import Brand, Organization
    from packages.db.models.affiliate_intel import (
        AffiliateNetworkAccount, AffiliateConversionEvent,
        AffiliateCommissionEvent, AffiliateLink,
    )
    from packages.db.session import get_sync_engine
    from packages.clients.analytics_clients import (
        AmazonAssociatesClient, ImpactCommissionClient,
    )

    engine = get_sync_engine()
    factory = get_async_session_factory()

    # Find all active affiliate network accounts
    async with factory() as db:
        network_accounts = (await db.execute(
            select(AffiliateNetworkAccount).where(
                AffiliateNetworkAccount.is_active.is_(True),
            )
        )).scalars().all()

        # Also get brand→org mapping for credential loading
        brands = (await db.execute(select(Brand).where(Brand.is_active.is_(True)))).scalars().all()
        brand_org_map = {b.id: b.organization_id for b in brands if b.organization_id}

    # Load credentials per org (sync path)
    creds_by_org: dict[uuid.UUID, dict] = {}
    with SyncSession(engine) as sync_session:
        for org_id in set(brand_org_map.values()):
            if org_id not in creds_by_org:
                creds_by_org[org_id] = _load_analytics_credentials(sync_session, org_id)
                # Also load affiliate-specific creds
                try:
                    from packages.clients.credential_loader import load_credential
                    creds_by_org[org_id]["amazon_access_key"] = load_credential(sync_session, org_id, "amazon_associates")
                    creds_by_org[org_id]["amazon_secret_key"] = load_credential(sync_session, org_id, "amazon_associates_secret")
                    creds_by_org[org_id]["amazon_tag"] = load_credential(sync_session, org_id, "amazon_associates_tag")
                    creds_by_org[org_id]["impact_account_sid"] = load_credential(sync_session, org_id, "impact_radius")
                    creds_by_org[org_id]["impact_auth_token"] = load_credential(sync_session, org_id, "impact_radius_token")
                except Exception:
                    pass

    synced = 0
    errors = 0

    for na in network_accounts:
        org_id = brand_org_map.get(na.brand_id)
        creds = creds_by_org.get(org_id, {}) if org_id else {}
        network = na.network_name.lower()

        try:
            commissions = []

            if "amazon" in network:
                client = AmazonAssociatesClient(
                    access_key=creds.get("amazon_access_key"),
                    secret_key=creds.get("amazon_secret_key"),
                    partner_tag=creds.get("amazon_tag"),
                )
                if client.is_configured():
                    result = await client.fetch_earnings(days=7)
                    commissions = result.get("commissions", [])

            elif "impact" in network:
                client = ImpactCommissionClient(
                    account_sid=creds.get("impact_account_sid"),
                    auth_token=creds.get("impact_auth_token"),
                )
                if client.is_configured():
                    result = await client.fetch_actions(days=7)
                    commissions = result.get("commissions", [])

            if commissions:
                async with factory() as db:
                    for c in commissions:
                        commission_amount = float(c.get("ad_fees", 0) or c.get("payout", 0))
                        sale_amount = float(c.get("revenue", 0) or c.get("sale_amount", 0))

                        if commission_amount <= 0 and sale_amount <= 0:
                            continue

                        # Try to match to an existing affiliate link via sub_id
                        link_id = None
                        offer_id = na.id  # Default to network account
                        sub_id = c.get("sub_id_1", "") or c.get("tag", "")
                        if sub_id:
                            link = (await db.execute(
                                select(AffiliateLink).where(
                                    AffiliateLink.brand_id == na.brand_id,
                                    AffiliateLink.is_active.is_(True),
                                ).limit(1)
                            )).scalar_one_or_none()
                            if link:
                                link_id = link.id
                                offer_id = link.offer_id

                        # Create conversion event
                        conv = AffiliateConversionEvent(
                            brand_id=na.brand_id,
                            link_id=link_id or na.id,
                            offer_id=offer_id,
                            conversion_value=sale_amount,
                            conversion_type="sale",
                            converted_at=datetime.now(timezone.utc),
                        )
                        db.add(conv)
                        await db.flush()

                        # Create commission event
                        db.add(AffiliateCommissionEvent(
                            brand_id=na.brand_id,
                            conversion_id=conv.id,
                            commission_amount=commission_amount,
                            commission_status="pending" if "pending" in c.get("status", "").lower() else "confirmed",
                        ))
                        synced += 1

                    await db.commit()

        except Exception as e:
            logger.warning(
                "affiliate_commission_sync.failed",
                network=network, brand_id=str(na.brand_id), error=str(e),
            )
            errors += 1

    logger.info("affiliate_commission_sync.complete", synced=synced, errors=errors)
    return {"commissions_synced": synced, "errors": errors}
