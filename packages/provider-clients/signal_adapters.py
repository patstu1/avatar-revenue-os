"""Signal adapter interfaces and implementations.

Adapters ingest signals from various sources into the unified topic_candidates
and trend_signals tables. Each adapter implements the SignalAdapter protocol.
"""
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


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


class GenericTrendFeedAdapter(SignalAdapter):
    """Interface for external trend data feeds (Google Trends, social APIs, etc).
    Concrete implementations require live API credentials.
    """

    def adapter_name(self) -> str:
        return "trend_feed"

    def fetch_signals(self, brand_id: uuid.UUID, config: dict) -> list[RawSignal]:
        # Placeholder — concrete implementations need API credentials
        return []


class GenericOfferInventoryAdapter(SignalAdapter):
    """Interface for external offer/affiliate network feeds.
    Concrete implementations require network API credentials.
    """

    def adapter_name(self) -> str:
        return "offer_inventory"

    def fetch_signals(self, brand_id: uuid.UUID, config: dict) -> list[RawSignal]:
        return []


ADAPTER_REGISTRY: dict[str, type[SignalAdapter]] = {
    "internal_performance": InternalPerformanceAdapter,
    "internal_comments": InternalCommentsAdapter,
    "manual_seed": ManualSeedAdapter,
    "trend_feed": GenericTrendFeedAdapter,
    "offer_inventory": GenericOfferInventoryAdapter,
}
