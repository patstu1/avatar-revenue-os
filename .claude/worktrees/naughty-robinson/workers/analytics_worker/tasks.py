"""Analytics worker tasks — trend scanning, performance ingestion, saturation checks."""
import logging

from workers.celery_app import app
from workers.base_task import TrackedTask
from packages.db.session import run_async

logger = logging.getLogger(__name__)


@app.task(base=TrackedTask, bind=True, name="workers.analytics_worker.tasks.scan_trends")
def scan_trends(self) -> dict:
    """Scan all configured trend sources and ingest new signals across all brands."""
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from packages.db.session import get_sync_engine
    from packages.db.models.publishing import SignalIngestionRun
    from packages.db.models.core import Brand
    from packages.db.enums import JobStatus
    from datetime import datetime, timezone

    engine = get_sync_engine()
    total_processed = 0
    with Session(engine) as session:
        brands = session.execute(select(Brand.id)).scalars().all()
        for brand_id in brands:
            run = SignalIngestionRun(
                brand_id=brand_id,
                source_type="trend_scan",
                status=JobStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
            )
            session.add(run)
            session.flush()

            import asyncio
            from packages.clients.trend_data_clients import (
                YouTubeTrendingClient, GoogleTrendsClient,
                RedditTrendingClient, TikTokTrendClient,
            )
            from packages.db.models.discovery import TrendSignal
            from packages.db.enums import SignalStrength

            fetched_signals: list[dict] = []
            clients = [
                ("youtube", YouTubeTrendingClient()),
                ("google_trends", GoogleTrendsClient()),
                ("reddit", RedditTrendingClient()),
                ("tiktok", TikTokTrendClient()),
            ]

            async def _gather_trends():
                results = []
                for src, cli in clients:
                    try:
                        if src == "youtube":
                            r = await cli.fetch_trending()
                        elif src == "google_trends":
                            r = await cli.fetch_daily_trends()
                        elif src == "reddit":
                            r = await cli.fetch_rising()
                        elif src == "tiktok":
                            r = await cli.fetch_trending_hashtags()
                        else:
                            continue
                        if r.get("success"):
                            for item in r.get("data", []):
                                results.append({"source": src, **item})
                    except Exception:
                        logger.debug("trend fetch failed for source %s", src, exc_info=True)
                return results

            try:
                fetched_signals = run_async(_gather_trends())
            except Exception:
                logger.warning("trend gathering failed for brand %s", brand_id, exc_info=True)

            for sig in fetched_signals:
                keyword = sig.get("title") or sig.get("hashtag") or sig.get("query") or ""
                if not keyword:
                    continue
                volume = int(sig.get("views", 0) or sig.get("video_count", 0) or sig.get("score", 0) or 0)
                velocity = float(sig.get("view_count", 0) or sig.get("num_comments", 0) or 0)
                strength = SignalStrength.STRONG if volume > 100_000 else (
                    SignalStrength.MODERATE if volume > 10_000 else SignalStrength.WEAK
                )
                session.add(TrendSignal(
                    brand_id=brand_id,
                    platform=sig.get("source", "unknown"),
                    signal_type="trend_scan",
                    keyword=keyword[:500],
                    volume=volume,
                    velocity=velocity,
                    strength=strength,
                    is_actionable=strength in (SignalStrength.STRONG, SignalStrength.MODERATE),
                    metadata_blob={"raw": {k: v for k, v in sig.items() if k not in ("source",)}},
                ))
                total_processed += 1

            run.status = JobStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            run.records_fetched = len(fetched_signals)
            run.records_processed = total_processed
        session.commit()

    return {"status": "completed", "brands_scanned": len(brands), "records_processed": total_processed}


@app.task(base=TrackedTask, bind=True, name="workers.analytics_worker.tasks.ingest_performance")
def ingest_performance(self) -> dict:
    """Pull performance metrics from all connected platform accounts.

    Iterates all active creator accounts, calls the platform API adapter for
    each, and persists PerformanceMetric rows. This is the critical bridge
    that feeds the entire intelligence layer.
    """
    from sqlalchemy.orm import Session
    from sqlalchemy import select, func
    from packages.db.session import get_sync_engine
    from packages.db.models.accounts import CreatorAccount
    from packages.db.models.publishing import PerformanceMetric
    from datetime import datetime, timezone

    engine = get_sync_engine()
    accounts_processed = 0
    metrics_created = 0

    with Session(engine) as session:
        accounts = session.execute(
            select(CreatorAccount).where(CreatorAccount.is_active.is_(True))
        ).scalars().all()

        for account in accounts:
            accounts_processed += 1
            try:
                import asyncio
                import os
                from packages.clients.external_clients import BufferClient

                if os.environ.get("BUFFER_API_KEY") and hasattr(account.platform, 'value'):
                    platform_val = account.platform.value if hasattr(account.platform, 'value') else str(account.platform)
                    if platform_val in ("youtube", "tiktok", "instagram", "twitter", "facebook", "linkedin"):
                        client = BufferClient()
                        result = run_async(client.get_profiles())
                        if result.get("success") and result.get("data"):
                            profiles = result["data"] if isinstance(result["data"], list) else []
                            for prof in profiles:
                                stats = prof.get("statistics", {})
                                if stats:
                                    session.add(PerformanceMetric(
                                        brand_id=account.brand_id,
                                        content_item_id=None,
                                        creator_account_id=account.id,
                                        platform=account.platform,
                                        impressions=int(stats.get("reach", 0)),
                                        views=int(stats.get("views", 0)),
                                        likes=int(stats.get("likes", 0)),
                                        clicks=int(stats.get("clicks", 0)),
                                        followers_gained=int(stats.get("new_followers", 0)),
                                        engagement_rate=float(stats.get("engagement_rate", 0)),
                                        revenue=0.0,
                                        measured_at=datetime.now(timezone.utc),
                                    ))
                                    metrics_created += 1

                from packages.db.models.content import ContentItem
                from packages.db.models.buffer_distribution import BufferPublishJob
                published_items = session.execute(
                    select(ContentItem).where(
                        ContentItem.creator_account_id == account.id,
                        ContentItem.status == "published",
                    ).order_by(ContentItem.created_at.desc()).limit(20)
                ).scalars().all()
                for ci in published_items:
                    existing = session.execute(
                        select(PerformanceMetric).where(
                            PerformanceMetric.content_item_id == ci.id,
                        ).limit(1)
                    ).scalar_one_or_none()
                    if not existing:
                        aff_revenue = 0.0
                        try:
                            from packages.db.models.affiliate_intel import AffiliateConversionEvent
                            convs = session.execute(
                                select(func.coalesce(func.sum(AffiliateConversionEvent.conversion_value), 0)).where(
                                    AffiliateConversionEvent.brand_id == account.brand_id,
                                )
                            ).scalar() or 0.0
                            aff_revenue = float(convs) / max(len(published_items), 1)
                        except Exception:
                            logger.debug("affiliate revenue lookup failed", exc_info=True)
                        session.add(PerformanceMetric(
                            brand_id=account.brand_id,
                            content_item_id=ci.id,
                            creator_account_id=account.id,
                            platform=account.platform,
                            impressions=0, views=0, likes=0, clicks=0,
                            followers_gained=0, engagement_rate=0.0,
                            revenue=aff_revenue,
                            measured_at=datetime.now(timezone.utc),
                        ))
                        metrics_created += 1
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("ingest_performance error for %s: %s", account.id, exc)

        # ── Brand-level fallback: pick up published content without a creator account ──
        from packages.db.models.content import ContentItem
        from packages.db.models.core import Brand
        try:
            all_brands = session.execute(select(Brand).where(Brand.is_active.is_(True))).scalars().all()
            for brand in all_brands:
                orphan_items = session.execute(
                    select(ContentItem).where(
                        ContentItem.brand_id == brand.id,
                        ContentItem.creator_account_id.is_(None),
                        ContentItem.status == "published",
                    ).order_by(ContentItem.created_at.desc()).limit(20)
                ).scalars().all()

                fallback_account = session.execute(
                    select(CreatorAccount).where(
                        CreatorAccount.brand_id == brand.id,
                        CreatorAccount.is_active.is_(True),
                    ).order_by(CreatorAccount.created_at).limit(1)
                ).scalar_one_or_none()

                for ci in orphan_items:
                    if fallback_account:
                        ci.creator_account_id = fallback_account.id
                        ci.platform = ci.platform or (fallback_account.platform.value if hasattr(fallback_account.platform, "value") else str(fallback_account.platform))

                    existing = session.execute(
                        select(PerformanceMetric).where(
                            PerformanceMetric.content_item_id == ci.id,
                        ).limit(1)
                    ).scalar_one_or_none()
                    if not existing and fallback_account:
                        session.add(PerformanceMetric(
                            brand_id=brand.id,
                            content_item_id=ci.id,
                            creator_account_id=fallback_account.id,
                            platform=fallback_account.platform,
                            impressions=0, views=0, likes=0, clicks=0,
                            followers_gained=0, engagement_rate=0.0,
                            revenue=0.0,
                            measured_at=datetime.now(timezone.utc),
                        ))
                        metrics_created += 1
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("orphan content ingestion error: %s", exc)

        session.commit()

    return {
        "status": "completed",
        "accounts_processed": accounts_processed,
        "metrics_created": metrics_created,
    }


@app.task(base=TrackedTask, bind=True, name="workers.analytics_worker.tasks.sync_youtube_analytics")
def sync_youtube_analytics(self) -> dict:
    """Sync YouTube analytics for all accounts with stored credentials."""
    import asyncio
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from packages.db.session import get_sync_engine
    from packages.db.models.accounts import CreatorAccount

    engine = get_sync_engine()
    accounts_synced = 0
    total_metrics = 0
    errors = []

    with Session(engine) as session:
        youtube_accounts = session.execute(
            select(CreatorAccount).where(
                CreatorAccount.is_active.is_(True),
                CreatorAccount.platform_access_token.isnot(None),
                CreatorAccount.credential_status == "connected",
            )
        ).scalars().all()

        yt_accounts = [a for a in youtube_accounts
                       if (a.platform.value if hasattr(a.platform, 'value') else str(a.platform)) == "youtube"]

    if not yt_accounts:
        return {"status": "completed", "accounts_synced": 0, "message": "No YouTube accounts with credentials"}

    from apps.api.services.youtube_sync_service import sync_youtube_account
    from packages.db.session import async_session_factory as _async_sf

    async def _run_sync():
        nonlocal accounts_synced, total_metrics
        async with _async_sf() as db:
            for acct_stub in yt_accounts:
                acct = (await db.execute(
                    select(CreatorAccount).where(CreatorAccount.id == acct_stub.id)
                )).scalar_one_or_none()
                if not acct:
                    continue
                try:
                    result = await sync_youtube_account(db, acct)
                    if result.get("status") == "completed":
                        accounts_synced += 1
                        total_metrics += result.get("metrics_synced", 0)
                    else:
                        errors.append({"account": str(acct.id), "error": result.get("error", result.get("status"))})
                except Exception as e:
                    errors.append({"account": str(acct.id), "error": str(e)})
            await db.commit()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run_sync())
    finally:
        loop.close()

    return {
        "status": "completed",
        "accounts_synced": accounts_synced,
        "metrics_synced": total_metrics,
        "errors": errors[:10],
    }


@app.task(base=TrackedTask, bind=True, name="workers.analytics_worker.tasks.recompute_revenue_forecast")
def recompute_revenue_forecast(self) -> dict:
    """Generate revenue forecasts for all active brands using the scoring engine."""
    import asyncio
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from packages.db.session import get_sync_engine
    from packages.db.models.core import Brand

    engine = get_sync_engine()
    brands_processed = 0
    errors = []

    with Session(engine) as session:
        brands = session.execute(select(Brand).where(Brand.is_active.is_(True))).scalars().all()
        for brand in brands:
            try:
                from packages.scoring.revenue_intelligence import forecast_revenue
                from packages.db.models.publishing import PerformanceMetric
                from sqlalchemy import func
                from datetime import datetime, timezone, timedelta

                cutoff = datetime.now(timezone.utc) - timedelta(days=90)
                metrics = session.execute(
                    select(PerformanceMetric).where(
                        PerformanceMetric.brand_id == brand.id,
                        PerformanceMetric.measured_at >= cutoff,
                    ).order_by(PerformanceMetric.measured_at)
                ).scalars().all()

                history = [
                    {"date": m.measured_at.isoformat() if m.measured_at else "", "revenue": float(m.revenue or 0)}
                    for m in metrics
                ]
                forecast_revenue(history)
                brands_processed += 1
            except Exception as exc:
                errors.append({"brand_id": str(brand.id), "error": str(exc)})

    return {"status": "completed", "brands_processed": brands_processed, "errors": errors[:10]}


@app.task(base=TrackedTask, bind=True, name="workers.analytics_worker.tasks.check_revenue_anomalies")
def check_revenue_anomalies(self) -> dict:
    """Detect revenue anomalies across all active brands."""
    from sqlalchemy.orm import Session
    from sqlalchemy import select, func
    from packages.db.session import get_sync_engine
    from packages.db.models.core import Brand
    from packages.db.models.publishing import PerformanceMetric
    from datetime import datetime, timezone, timedelta

    engine = get_sync_engine()
    brands_checked = 0
    anomalies_found = 0

    with Session(engine) as session:
        brands = session.execute(select(Brand).where(Brand.is_active.is_(True))).scalars().all()
        now = datetime.now(timezone.utc)

        for brand in brands:
            brands_checked += 1
            try:
                avg_7d = session.execute(
                    select(func.avg(PerformanceMetric.revenue)).where(
                        PerformanceMetric.brand_id == brand.id,
                        PerformanceMetric.measured_at >= now - timedelta(days=7),
                    )
                ).scalar() or 0.0

                avg_30d = session.execute(
                    select(func.avg(PerformanceMetric.revenue)).where(
                        PerformanceMetric.brand_id == brand.id,
                        PerformanceMetric.measured_at >= now - timedelta(days=30),
                    )
                ).scalar() or 0.0

                if avg_30d > 0 and abs(avg_7d - avg_30d) / avg_30d > 0.3:
                    anomalies_found += 1
            except Exception:
                logger.debug("revenue anomaly check failed for brand %s", brand.id, exc_info=True)

    return {"status": "completed", "brands_checked": brands_checked, "anomalies_found": anomalies_found}


@app.task(base=TrackedTask, bind=True, name="workers.analytics_worker.tasks.check_saturation")
def check_saturation(self) -> dict:
    """Run saturation/fatigue analysis across all active accounts.

    Reads recent PerformanceMetric data and identifies accounts showing
    declining engagement (saturation signal).
    """
    from sqlalchemy.orm import Session
    from sqlalchemy import select, func
    from packages.db.session import get_sync_engine
    from packages.db.models.accounts import CreatorAccount
    from packages.db.models.publishing import PerformanceMetric

    engine = get_sync_engine()
    accounts_analyzed = 0
    saturation_flags = 0

    with Session(engine) as session:
        accounts = session.execute(
            select(CreatorAccount).where(CreatorAccount.is_active.is_(True))
        ).scalars().all()

        for account in accounts:
            accounts_analyzed += 1
            metric_count = session.execute(
                select(func.count()).select_from(PerformanceMetric).where(
                    PerformanceMetric.creator_account_id == account.id
                )
            ).scalar() or 0

            if metric_count == 0:
                continue

            from packages.scoring.saturation import SaturationInput, compute_saturation
            from packages.db.models.content import ContentItem
            from datetime import datetime, timezone, timedelta

            now = datetime.now(timezone.utc)
            cutoff_7d = now - timedelta(days=7)
            cutoff_30d = now - timedelta(days=30)

            posts_7d = session.execute(
                select(func.count()).select_from(ContentItem).where(
                    ContentItem.creator_account_id == account.id,
                    ContentItem.status == "published",
                    ContentItem.created_at >= cutoff_7d,
                )
            ).scalar() or 0
            posts_30d = session.execute(
                select(func.count()).select_from(ContentItem).where(
                    ContentItem.creator_account_id == account.id,
                    ContentItem.status == "published",
                    ContentItem.created_at >= cutoff_30d,
                )
            ).scalar() or 0

            avg_eng_7d = session.execute(
                select(func.avg(PerformanceMetric.engagement_rate)).where(
                    PerformanceMetric.creator_account_id == account.id,
                    PerformanceMetric.measured_at >= cutoff_7d,
                )
            ).scalar() or 0.0
            avg_eng_30d = session.execute(
                select(func.avg(PerformanceMetric.engagement_rate)).where(
                    PerformanceMetric.creator_account_id == account.id,
                    PerformanceMetric.measured_at >= cutoff_30d,
                )
            ).scalar() or 0.0

            sat_input = SaturationInput(
                total_posts_in_niche=int(posts_30d),
                posts_last_30d=int(posts_30d),
                posts_last_7d=int(posts_7d),
                unique_topics_covered=max(1, int(posts_30d) // 3),
                total_topics_available=max(1, int(posts_30d)),
                avg_engagement_last_7d=float(avg_eng_7d),
                avg_engagement_last_30d=float(avg_eng_30d),
            )
            result = compute_saturation(sat_input)

            account.saturation_score = result.saturation_score
            account.fatigue_score = result.fatigue_score

            if result.recommended_action in ("suppress", "reduce"):
                saturation_flags += 1

        session.commit()

    return {
        "status": "completed",
        "accounts_analyzed": accounts_analyzed,
        "saturation_flags": saturation_flags,
    }
