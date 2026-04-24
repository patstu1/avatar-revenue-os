"""Trend / Viral Opportunity Service — scan, score, persist, suppress."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.core import Brand
from packages.db.models.discovery import TrendSignal as DiscoveryTrend
from packages.db.models.trend_viral import (
    TrendBlocker,
    TrendDuplicate,
    TrendOpportunityScore,
    TrendSignalEvent,
    TrendSourceHealth,
    TrendSuppressionRule,
    TrendVelocityReport,
    ViralOpportunity,
)
from packages.scoring.trend_viral_engine import (
    check_duplicate,
    classify_opportunity,
    compute_velocity,
    detect_blockers,
    extract_signals,
    score_opportunity,
    should_suppress,
)

logger = logging.getLogger(__name__)

# ── Platform → content format mapping for cross-platform replication ────────
PLATFORM_CONTENT_MAP: dict[str, dict[str, Any]] = {
    "tiktok": {"content_type": "short_video", "target_duration_seconds": 45, "tone": "Energetic, punchy, trend-native"},
    "instagram": {
        "content_type": "short_video",
        "target_duration_seconds": 30,
        "tone": "Polished, visual-first, aspirational",
    },
    "youtube": {"content_type": "short_video", "target_duration_seconds": 58, "tone": "Urgent, informative, timely"},
    "x": {"content_type": "text_post", "target_duration_seconds": 0, "tone": "Sharp, witty, conversational"},
    "twitter": {"content_type": "text_post", "target_duration_seconds": 0, "tone": "Sharp, witty, conversational"},
    "facebook": {"content_type": "static_image", "target_duration_seconds": 0, "tone": "Relatable, shareable"},
    "linkedin": {"content_type": "text_post", "target_duration_seconds": 0, "tone": "Professional, insightful"},
    "threads": {"content_type": "text_post", "target_duration_seconds": 0, "tone": "Casual, conversational"},
    "pinterest": {"content_type": "static_image", "target_duration_seconds": 0, "tone": "Visual, aspirational"},
    "reddit": {"content_type": "text_post", "target_duration_seconds": 0, "tone": "Authentic, community-native"},
    "snapchat": {"content_type": "story", "target_duration_seconds": 15, "tone": "Fun, raw, behind-the-scenes"},
}


async def _fetch_external_trends(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    """Fetch from ALL configured external trend sources in parallel.

    No artificial result count limits — fetches everything each API returns.
    Gets API keys via integration_manager for each source.
    """
    from apps.api.services.integration_manager import get_credential
    from packages.clients.trend_data_clients import (
        GoogleTrendsClient,
        RedditTrendingClient,
        TikTokTrendClient,
        YouTubeTrendingClient,
    )

    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        return []
    org_id = brand.organization_id
    niche = brand.niche or "general"

    # Resolve credentials for each source
    google_key = await get_credential(db, org_id, "gemini_flash") or ""  # YouTube Data API shares Google key
    # Reddit and TikTok Creative Center endpoints are public — no key required
    # Google Trends unofficial API is public — no key required

    # Build all fetch tasks — no result count caps
    tasks: list[tuple[str, Any]] = []

    # YouTube trending — fetch max page (50 is API max per request)
    if google_key:
        yt = YouTubeTrendingClient(api_key=google_key)
        tasks.append(("youtube_trending", yt.fetch_trending(max_results=50)))
        tasks.append(("youtube_search", yt.search_trending_topics(query=niche, max_results=50)))

    # Google Trends — public, no key needed
    gt = GoogleTrendsClient()
    tasks.append(("google_trends", gt.fetch_daily_trends()))

    # Reddit — public JSON endpoints, no key needed
    reddit = RedditTrendingClient()
    tasks.append(("reddit_popular", reddit.fetch_rising(limit=100)))
    # Also fetch niche-specific subreddits based on brand niche
    niche_subs = _niche_to_subreddits(niche)
    if niche_subs:
        tasks.append(("reddit_niche", reddit.fetch_niche_trends(niche_subs, limit=100)))

    # TikTok Creative Center — public endpoint
    tt = TikTokTrendClient()
    tasks.append(("tiktok_hashtags", tt.fetch_trending_hashtags()))

    # Execute all in parallel
    names = [t[0] for t in tasks]
    coros = [t[1] for t in tasks]
    results = await asyncio.gather(*coros, return_exceptions=True)

    # Normalize all results into unified signal format
    all_signals: list[dict[str, Any]] = []
    source_health: dict[str, dict] = {}

    for name, result in zip(names, results):
        if isinstance(result, Exception):
            logger.warning("external_trend_source_failed source=%s error=%s", name, result)
            source_health[name] = {"status": "error", "count": 0, "error": str(result)}
            continue
        if not result.get("success"):
            source_health[name] = {"status": "error", "count": 0, "error": result.get("error", "unknown")}
            continue

        items = result.get("data", [])
        source_health[name] = {"status": "healthy", "count": len(items)}

        for item in items:
            signal = _normalize_external_signal(name, item)
            if signal:
                all_signals.append(signal)

    # Persist source health records
    for src_name, health in source_health.items():
        db.add(
            TrendSourceHealth(
                brand_id=brand_id,
                source_name=src_name,
                status=health["status"],
                last_signal_count=health["count"],
                truth_label="external_api",
            )
        )

    return all_signals


def _normalize_external_signal(source_name: str, item: dict) -> dict[str, Any] | None:
    """Convert a source-specific item into unified signal dict."""
    topic = ""
    strength = 0.0
    velocity = 0.0

    if source_name.startswith("youtube"):
        topic = item.get("title", "")
        views = item.get("views", 0)
        likes = item.get("likes", 0)
        strength = float(views) if views else 0.0
        velocity = float(likes) / max(float(views), 1.0) * 100 if views else 0.0

    elif source_name == "google_trends":
        topic = item.get("title", "")
        traffic_str = item.get("traffic", "0")
        traffic_str = traffic_str.replace("+", "").replace(",", "").replace("K", "000").replace("M", "000000")
        try:
            strength = float(traffic_str)
        except ValueError:
            strength = 0.0
        velocity = strength / 1000.0  # relative velocity proxy

    elif source_name.startswith("reddit"):
        topic = item.get("title", "")
        strength = float(item.get("score", 0))
        comments = float(item.get("num_comments", 0))
        velocity = (strength + comments * 2) / 100.0  # engagement velocity proxy

    elif source_name.startswith("tiktok"):
        topic = item.get("hashtag", "")
        view_count = item.get("view_count", 0)
        video_count = item.get("video_count", 0)
        strength = float(view_count)
        velocity = float(video_count) / 1000.0 if video_count else 0.0

    if not topic or len(topic) < 3:
        return None

    return {
        "topic": topic,
        "source": source_name,
        "signal_strength": strength,
        "velocity": velocity,
        "truth_label": "external_api",
    }


def _niche_to_subreddits(niche: str) -> list[str]:
    """Map brand niche to relevant subreddits for trend scanning."""
    niche_lower = (niche or "").lower()
    mapping: dict[str, list[str]] = {
        "tech": ["technology", "programming", "gadgets", "startups"],
        "fitness": ["fitness", "bodybuilding", "running", "nutrition"],
        "beauty": ["beauty", "makeupaddiction", "skincareaddiction"],
        "gaming": ["gaming", "pcgaming", "games", "indiegaming"],
        "finance": ["personalfinance", "investing", "cryptocurrency", "stocks"],
        "food": ["food", "cooking", "recipes", "foodporn"],
        "travel": ["travel", "backpacking", "solotravel"],
        "fashion": ["fashion", "malefashionadvice", "femalefashionadvice", "streetwear"],
        "music": ["music", "listentothis", "hiphopheads", "indieheads"],
        "education": ["education", "learnprogramming", "college", "studytips"],
        "health": ["health", "mentalhealth", "meditation", "nutrition"],
        "business": ["entrepreneur", "smallbusiness", "startups", "marketing"],
    }
    for key, subs in mapping.items():
        if key in niche_lower:
            return subs
    return ["popular", "all"]


async def light_scan(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    """60-second light scan: fetch ALL external + internal signals, compute deltas, dedup.

    Fetches from every configured external trend source in parallel via asyncio.gather,
    combines with internal DiscoveryTrend data, scores, deduplicates, and persists.
    No artificial result count limits on any source.
    """
    now = datetime.now(timezone.utc)

    # ── Internal discovery signals (no limit) ──────────────────────────
    discovery = list(
        (await db.execute(select(DiscoveryTrend).where(DiscoveryTrend.brand_id == brand_id))).scalars().all()
    )

    internal_raw = [
        {
            "topic": d.keyword or str(d.id)[:8],
            "source": "discovery",
            "signal_strength": float(d.volume or 0),
            "velocity": float(d.velocity or 0),
            "truth_label": "internal_proxy",
        }
        for d in discovery
    ]

    # ── External API signals (parallel, no caps) ───────────────────────
    external_raw = await _fetch_external_trends(db, brand_id)

    # ── Combine all signals ────────────────────────────────────────────
    raw = internal_raw + external_raw

    existing = list(
        (
            await db.execute(
                select(TrendSignalEvent.topic).where(
                    TrendSignalEvent.brand_id == brand_id,
                    TrendSignalEvent.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    signals = extract_signals(raw, existing)

    # ── Deduplicate and persist ────────────────────────────────────────
    created = 0
    updated = 0
    for s in signals:
        if s.get("is_new"):
            db.add(
                TrendSignalEvent(
                    brand_id=brand_id,
                    source=s["source"],
                    topic=s["topic"],
                    signal_strength=s["signal_strength"],
                    velocity=s["velocity"],
                    first_seen_at=now,
                    last_seen_at=now,
                    truth_label=s["truth_label"],
                )
            )
            created += 1
        else:
            existing_sig = (
                await db.execute(
                    select(TrendSignalEvent)
                    .where(
                        TrendSignalEvent.brand_id == brand_id,
                        TrendSignalEvent.topic == s["topic"],
                        TrendSignalEvent.is_active.is_(True),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existing_sig:
                existing_sig.last_seen_at = now
                existing_sig.velocity = max(existing_sig.velocity or 0, s["velocity"])
                existing_sig.signal_strength = max(existing_sig.signal_strength or 0, s["signal_strength"])
                updated += 1

    await db.flush()
    return {
        "signals_scanned": len(raw),
        "internal_signals": len(internal_raw),
        "external_signals": len(external_raw),
        "new_signals": created,
        "updated_signals": updated,
        "status": "completed",
    }


async def deep_analysis(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    """Deeper analysis on threshold-crossing signals — create opportunities."""
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    brand_ctx = {"niche": brand.niche if brand else "general"}
    has_accounts = (
        await db.execute(
            select(CreatorAccount.id)
            .where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
            .limit(1)
        )
    ).scalar() is not None

    signals = list(
        (
            await db.execute(
                select(TrendSignalEvent).where(
                    TrendSignalEvent.brand_id == brand_id,
                    TrendSignalEvent.is_active.is_(True),
                    TrendSignalEvent.velocity > 0.5,
                )
            )
        )
        .scalars()
        .all()
    )
    suppressions = list(
        (
            await db.execute(
                select(TrendSuppressionRule).where(
                    TrendSuppressionRule.brand_id == brand_id, TrendSuppressionRule.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    supp_dicts = [{"pattern": s.pattern, "reason": s.reason} for s in suppressions]

    existing_opps = list(
        (
            await db.execute(
                select(ViralOpportunity.topic).where(
                    ViralOpportunity.brand_id == brand_id, ViralOpportunity.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )

    await db.execute(delete(TrendBlocker).where(TrendBlocker.brand_id == brand_id))
    now = datetime.now(timezone.utc)
    created = 0

    for sig in signals:
        dup = check_duplicate(sig.topic, existing_opps)
        if dup:
            db.add(TrendDuplicate(brand_id=brand_id, original_topic=dup, duplicate_topic=sig.topic, similarity=0.7))
            continue

        sig_dict = {
            "topic": sig.topic,
            "source": sig.source,
            "velocity": float(sig.velocity),
            "signal_strength": float(sig.signal_strength),
            "is_new": True,
            "truth_label": sig.truth_label,
        }
        scores = score_opportunity(sig_dict, brand_ctx)
        suppressed = should_suppress(sig_dict, scores, supp_dicts)
        if suppressed:
            continue

        classification = classify_opportunity(scores)
        blockers = detect_blockers(sig_dict, {"has_accounts": has_accounts})

        vel = compute_velocity(float(sig.velocity), 0)
        db.add(
            TrendVelocityReport(
                brand_id=brand_id,
                topic=sig.topic,
                current_velocity=vel["current_velocity"],
                previous_velocity=vel["previous_velocity"],
                acceleration=vel["acceleration"],
                breakout=vel["breakout"],
            )
        )

        opp = ViralOpportunity(
            brand_id=brand_id,
            topic=sig.topic,
            source=sig.source,
            first_seen_at=sig.first_seen_at,
            last_seen_at=now,
            **scores,
            **classification,
            explanation=f"{classification['opportunity_type']} opportunity — {sig.topic}",
            truth_label=sig.truth_label,
        )
        db.add(opp)
        await db.flush()

        for dim in [
            "velocity",
            "novelty",
            "relevance",
            "revenue_potential",
            "platform_fit",
            "account_fit",
            "content_form_fit",
        ]:
            db.add(TrendOpportunityScore(opportunity_id=opp.id, dimension=dim, score=scores.get(f"{dim}_score", 0)))

        for b in blockers:
            db.add(TrendBlocker(brand_id=brand_id, opportunity_id=opp.id, **b))

        existing_opps.append(sig.topic)
        created += 1

    db.add(
        TrendSourceHealth(
            brand_id=brand_id,
            source_name="discovery",
            status="healthy" if signals else "no_signals",
            last_signal_count=len(signals),
            truth_label="internal_proxy",
        )
    )

    await db.flush()
    return {"rows_processed": len(signals), "opportunities_created": created, "status": "completed"}


async def list_signals(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(TrendSignalEvent)
                .where(TrendSignalEvent.brand_id == brand_id, TrendSignalEvent.is_active.is_(True))
                .order_by(TrendSignalEvent.velocity.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )


async def list_velocity(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(TrendVelocityReport)
                .where(TrendVelocityReport.brand_id == brand_id, TrendVelocityReport.is_active.is_(True))
                .order_by(TrendVelocityReport.current_velocity.desc())
            )
        )
        .scalars()
        .all()
    )


async def list_opportunities(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(ViralOpportunity)
                .where(ViralOpportunity.brand_id == brand_id, ViralOpportunity.is_active.is_(True))
                .order_by(ViralOpportunity.composite_score.desc())
            )
        )
        .scalars()
        .all()
    )


async def list_blockers(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(TrendBlocker).where(TrendBlocker.brand_id == brand_id, TrendBlocker.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )


async def list_source_health(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list(
        (
            await db.execute(
                select(TrendSourceHealth).where(
                    TrendSourceHealth.brand_id == brand_id, TrendSourceHealth.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )


async def get_top_opportunities(db: AsyncSession, brand_id: uuid.UUID, limit: int = 5) -> list[dict[str, Any]]:
    """Downstream: top trend opportunities for copilot/generation."""
    opps = list(
        (
            await db.execute(
                select(ViralOpportunity)
                .where(
                    ViralOpportunity.brand_id == brand_id,
                    ViralOpportunity.is_active.is_(True),
                    ViralOpportunity.status == "active",
                )
                .order_by(ViralOpportunity.composite_score.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "topic": o.topic,
            "score": o.composite_score,
            "type": o.opportunity_type,
            "platform": o.recommended_platform,
            "form": o.recommended_content_form,
            "monetization": o.recommended_monetization,
            "urgency": o.urgency,
        }
        for o in opps
    ]
