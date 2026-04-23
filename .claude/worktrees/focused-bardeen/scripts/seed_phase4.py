"""Phase 4 seed: performance metrics, attribution events, memory entries.
Run: docker exec aro-api python scripts/seed_phase4.py
"""
import sys, os, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.orm import Session
from packages.db.session import get_sync_engine
from packages.db.models.core import Brand
from packages.db.models.content import ContentItem
from packages.db.models.accounts import CreatorAccount
from packages.db.models.offers import Offer
from packages.db.models.publishing import PerformanceMetric, AttributionEvent
from packages.db.models.learning import MemoryEntry
from packages.db.enums import Platform

engine = get_sync_engine()


def seed():
    with Session(engine) as db:
        brand = db.execute(select(Brand).limit(1)).scalar_one_or_none()
        if not brand:
            print("No brands. Run seed.py first.")
            return

        existing = db.query(PerformanceMetric).filter(PerformanceMetric.brand_id == brand.id).first()
        if existing:
            print("Phase 4 already seeded. Skipping.")
            return

        bid = brand.id
        items = db.execute(select(ContentItem).where(ContentItem.brand_id == bid)).scalars().all()
        accounts = db.execute(select(CreatorAccount).where(CreatorAccount.brand_id == bid)).scalars().all()
        offers = db.execute(select(Offer).where(Offer.brand_id == bid)).scalars().all()

        if not items or not accounts:
            print("Need content items and accounts. Run seed_phase3.py first.")
            return

        acct = accounts[0]
        offer = offers[0] if offers else None

        metrics = []
        for i, item in enumerate(items):
            impressions = [12000, 8500, 3200][i % 3]
            clicks = int(impressions * [0.035, 0.025, 0.012][i % 3])
            revenue = [45.60, 28.30, 5.20][i % 3]

            pm = PerformanceMetric(
                content_item_id=item.id, creator_account_id=acct.id,
                brand_id=bid, platform=Platform.YOUTUBE,
                impressions=impressions, views=int(impressions * 0.85),
                likes=int(impressions * 0.04), comments=int(impressions * 0.008),
                shares=int(impressions * 0.005), saves=int(impressions * 0.003),
                clicks=clicks, ctr=round(clicks / impressions, 4),
                watch_time_seconds=int(impressions * 0.6 * 45),
                avg_watch_pct=0.62 if i == 0 else 0.45 if i == 1 else 0.28,
                followers_gained=[120, 45, 8][i % 3],
                revenue=revenue, revenue_source="adsense",
                rpm=round(revenue / impressions * 1000, 2),
                engagement_rate=round((int(impressions * 0.04) + int(impressions * 0.008) + int(impressions * 0.005)) / impressions, 4),
            )
            metrics.append(pm)
        db.add_all(metrics)

        events = []
        for i, item in enumerate(items[:2]):
            for j in range(5 - i * 2):
                events.append(AttributionEvent(
                    brand_id=bid, content_item_id=item.id,
                    offer_id=offer.id if offer else None,
                    creator_account_id=acct.id,
                    event_type="click", event_value=0.0, platform="youtube",
                    tracking_id=f"utm_{uuid.uuid4().hex[:8]}",
                ))
            for j in range(2 - i):
                events.append(AttributionEvent(
                    brand_id=bid, content_item_id=item.id,
                    offer_id=offer.id if offer else None,
                    creator_account_id=acct.id,
                    event_type="purchase", event_value=35.0, platform="youtube",
                    tracking_id=f"conv_{uuid.uuid4().hex[:8]}",
                ))
        db.add_all(events)

        memories = [
            MemoryEntry(brand_id=bid, memory_type="content_performance", category="winner",
                       key="winner:budget_hacks", value="Budget hacks topic consistently outperforms",
                       structured_value={"avg_rpm": 3.80, "avg_engagement": 0.053}, confidence=0.8),
            MemoryEntry(brand_id=bid, memory_type="audience_insight", category="preference",
                       key="audience:prefers_data", value="Audience responds best to data-driven content",
                       structured_value={"signal_count": 12}, confidence=0.75),
            MemoryEntry(brand_id=bid, memory_type="platform_learning", category="timing",
                       key="youtube:best_time", value="Tuesday/Thursday 9-11am EST performs best",
                       structured_value={"best_days": ["tuesday", "thursday"], "best_hours": [9, 10, 11]}, confidence=0.65),
        ]
        db.add_all(memories)
        db.commit()

        print(f"Phase 4 seed complete:")
        print(f"  {len(metrics)} performance metrics")
        print(f"  {len(events)} attribution events")
        print(f"  {len(memories)} memory entries")


if __name__ == "__main__":
    seed()
