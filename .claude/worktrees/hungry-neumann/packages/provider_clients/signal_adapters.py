"""Signal adapter interfaces and implementations.

Adapters ingest signals from various sources into the unified topic_candidates
and trend_signals tables. Each adapter implements the SignalAdapter protocol.
"""
import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger()


@dataclass
class RawSignal:
    source_type: str
    title: str
    keywords: list[str] = field(default_factory=list)
    description: str = ""
    category: str = ""
    platform: str = ""
    volume: int = 0
    velocity: float = 0.0
    buyer_intent_score: float = 0.0
    metadata: dict = field(default_factory=dict)


class SignalAdapter(ABC):
    """Base protocol for all signal adapters."""

    @abstractmethod
    def adapter_name(self) -> str: ...

    @abstractmethod
    def fetch_signals(self, brand_id: uuid.UUID, config: dict) -> list[RawSignal]: ...


class InternalPerformanceAdapter(SignalAdapter):
    """Reads historical performance data to find winning topics."""

    def adapter_name(self) -> str:
        return "internal_performance"

    def fetch_signals(self, brand_id: uuid.UUID, config: dict) -> list[RawSignal]:
        from sqlalchemy.orm import Session
        from packages.db.session import get_sync_engine
        from packages.db.models.publishing import PerformanceMetric

        engine = get_sync_engine()
        signals = []
        with Session(engine) as db:
            metrics = (
                db.query(PerformanceMetric)
                .filter(PerformanceMetric.brand_id == brand_id)
                .order_by(PerformanceMetric.revenue.desc())
                .limit(50)
                .all()
            )
            for m in metrics:
                if m.revenue > 0:
                    signals.append(RawSignal(
                        source_type="internal_performance",
                        title=f"High-revenue content signal (${m.revenue:.2f})",
                        keywords=[],
                        platform=m.platform.value if hasattr(m.platform, 'value') else str(m.platform),
                        volume=m.views,
                        velocity=m.engagement_rate,
                        buyer_intent_score=min(m.ctr * 10, 1.0),
                        metadata={"content_item_id": str(m.content_item_id), "revenue": m.revenue},
                    ))
        return signals


class InternalCommentsAdapter(SignalAdapter):
    """Reads comment data to find demand signals from the audience."""

    def adapter_name(self) -> str:
        return "internal_comments"

    def fetch_signals(self, brand_id: uuid.UUID, config: dict) -> list[RawSignal]:
        from sqlalchemy.orm import Session
        from packages.db.session import get_sync_engine
        from packages.db.models.learning import CommentIngestion

        engine = get_sync_engine()
        signals = []
        with Session(engine) as db:
            comments = (
                db.query(CommentIngestion)
                .filter(
                    CommentIngestion.brand_id == brand_id,
                    CommentIngestion.is_purchase_intent.is_(True),
                )
                .limit(50)
                .all()
            )
            for c in comments:
                signals.append(RawSignal(
                    source_type="internal_comments",
                    title=f"Purchase intent: {c.comment_text[:80]}",
                    keywords=[],
                    buyer_intent_score=0.7,
                    metadata={"comment_id": str(c.id), "intent": c.intent_classification},
                ))
        return signals


class ManualSeedAdapter(SignalAdapter):
    """Accepts manually provided topics as seeds."""

    def adapter_name(self) -> str:
        return "manual_seed"

    def fetch_signals(self, brand_id: uuid.UUID, config: dict) -> list[RawSignal]:
        topics = config.get("topics", [])
        signals = []
        for t in topics:
            signals.append(RawSignal(
                source_type="manual_seed",
                title=t.get("title", ""),
                keywords=t.get("keywords", []),
                description=t.get("description", ""),
                category=t.get("category", ""),
                volume=t.get("volume", 0),
                velocity=t.get("velocity", 0.0),
                buyer_intent_score=t.get("buyer_intent", 0.5),
                metadata=t.get("metadata", {}),
            ))
        return signals


def _run_async(coro):
    """Run an async coroutine from synchronous context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result(timeout=60)
    return asyncio.run(coro)


class GenericTrendFeedAdapter(SignalAdapter):
    """Fetches external trend data from Google Trends, YouTube, Reddit, and TikTok.

    Delegates to real trend clients from packages.clients.trend_data_clients.
    """

    def adapter_name(self) -> str:
        return "trend_feed"

    def fetch_signals(self, brand_id: uuid.UUID, config: dict) -> list[RawSignal]:
        from packages.clients.trend_data_clients import (
            GoogleTrendsClient, YouTubeTrendingClient,
            RedditTrendingClient, TikTokTrendClient,
        )

        signals: list[RawSignal] = []
        sources = config.get("sources", ["google_trends", "youtube", "reddit", "tiktok"])
        region = config.get("region", "US")
        query = config.get("query", "")
        subreddits = config.get("subreddits", ["popular"])

        async def _gather() -> list[RawSignal]:
            collected: list[RawSignal] = []

            if "google_trends" in sources:
                try:
                    result = await GoogleTrendsClient().fetch_daily_trends(geo=region)
                    if result.get("success"):
                        for item in result.get("data", []):
                            collected.append(RawSignal(
                                source_type="google_trends",
                                title=item.get("title", ""),
                                keywords=item.get("related_queries", []),
                                platform="google",
                                volume=int(item.get("traffic", "0").replace(",", "").replace("+", "") or 0),
                                metadata=item,
                            ))
                except Exception as e:
                    logger.warning("trend_feed.google_trends_error", error=str(e))

            if "youtube" in sources:
                try:
                    client = YouTubeTrendingClient()
                    result = await client.fetch_trending(region=region)
                    if result.get("success"):
                        for item in result.get("data", []):
                            collected.append(RawSignal(
                                source_type="youtube_trending",
                                title=item.get("title", ""),
                                keywords=item.get("tags", []),
                                platform="youtube",
                                volume=item.get("views", 0),
                                metadata=item,
                            ))
                except Exception as e:
                    logger.warning("trend_feed.youtube_error", error=str(e))

            if "reddit" in sources:
                try:
                    result = await RedditTrendingClient().fetch_niche_trends(subreddits)
                    if result.get("success"):
                        for item in result.get("data", []):
                            collected.append(RawSignal(
                                source_type="reddit_rising",
                                title=item.get("title", ""),
                                keywords=[],
                                platform="reddit",
                                volume=item.get("score", 0),
                                velocity=float(item.get("num_comments", 0)),
                                metadata=item,
                            ))
                except Exception as e:
                    logger.warning("trend_feed.reddit_error", error=str(e))

            if "tiktok" in sources:
                try:
                    result = await TikTokTrendClient().fetch_trending_hashtags(country=region)
                    if result.get("success"):
                        for item in result.get("data", []):
                            collected.append(RawSignal(
                                source_type="tiktok_hashtag",
                                title=item.get("hashtag", ""),
                                keywords=[item.get("hashtag", "")],
                                platform="tiktok",
                                volume=item.get("video_count", 0),
                                metadata=item,
                            ))
                except Exception as e:
                    logger.warning("trend_feed.tiktok_error", error=str(e))

            return collected

        try:
            signals = _run_async(_gather())
        except Exception as e:
            logger.error("trend_feed.fetch_failed", error=str(e))

        return signals


class GenericOfferInventoryAdapter(SignalAdapter):
    """Fetches external offer/affiliate inventory from Impact and ShareASale.

    Delegates to real affiliate network clients from packages.clients.affiliate_network_clients.
    """

    def adapter_name(self) -> str:
        return "offer_inventory"

    def fetch_signals(self, brand_id: uuid.UUID, config: dict) -> list[RawSignal]:
        from packages.clients.affiliate_network_clients import ImpactClient, ShareASaleClient

        signals: list[RawSignal] = []

        async def _gather() -> list[RawSignal]:
            collected: list[RawSignal] = []

            try:
                impact = ImpactClient()
                result = await impact.fetch_offers()
                if result.get("success"):
                    for offer in result.get("data", []):
                        name = offer.get("Name", "") or offer.get("name", "")
                        collected.append(RawSignal(
                            source_type="impact_offer",
                            title=name or "Impact campaign",
                            keywords=[],
                            category="affiliate",
                            platform="impact",
                            buyer_intent_score=0.6,
                            metadata=offer,
                        ))
            except Exception as e:
                logger.warning("offer_inventory.impact_error", error=str(e))

            try:
                sas = ShareASaleClient()
                result = await sas.fetch_merchants()
                if result.get("success"):
                    data = result.get("data", "")
                    if isinstance(data, str) and data.strip():
                        collected.append(RawSignal(
                            source_type="shareasale_merchants",
                            title="ShareASale merchant listings",
                            keywords=[],
                            category="affiliate",
                            platform="shareasale",
                            buyer_intent_score=0.5,
                            metadata={"raw_response": data[:2000]},
                        ))
            except Exception as e:
                logger.warning("offer_inventory.shareasale_error", error=str(e))

            return collected

        try:
            signals = _run_async(_gather())
        except Exception as e:
            logger.error("offer_inventory.fetch_failed", error=str(e))

        return signals


ADAPTER_REGISTRY: dict[str, type[SignalAdapter]] = {
    "internal_performance": InternalPerformanceAdapter,
    "internal_comments": InternalCommentsAdapter,
    "manual_seed": ManualSeedAdapter,
    "trend_feed": GenericTrendFeedAdapter,
    "offer_inventory": GenericOfferInventoryAdapter,
}
