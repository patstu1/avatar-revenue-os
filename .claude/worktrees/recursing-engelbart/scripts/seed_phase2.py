"""Phase 2 seed: populates discovery, scoring, and recommendation data.
Run: docker exec aro-api python scripts/seed_phase2.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.orm import Session
from packages.db.session import get_sync_engine
from packages.db.models.core import Brand
from packages.db.models.discovery import TopicSource, TopicCandidate, NicheCluster, TrendSignal
from packages.db.enums import SignalStrength

engine = get_sync_engine()


def seed():
    with Session(engine) as db:
        brand = db.execute(select(Brand).limit(1)).scalar_one_or_none()
        if not brand:
            print("No brands found. Run scripts/seed.py first.")
            return

        existing = db.query(TopicCandidate).filter(TopicCandidate.brand_id == brand.id).first()
        if existing:
            print("Phase 2 data already seeded. Skipping.")
            return

        bid = brand.id

        # Topic Sources
        sources = [
            TopicSource(brand_id=bid, source_type="manual_seed", source_config={"notes": "Initial topic research"}, is_active=True),
            TopicSource(brand_id=bid, source_type="internal_performance", source_config={}, is_active=True),
            TopicSource(brand_id=bid, source_type="trend_feed", source_config={"provider": "pending"}, is_active=False),
        ]
        db.add_all(sources)
        db.flush()

        # Topic Candidates
        topics = [
            TopicCandidate(brand_id=bid, source_id=sources[0].id, title="How to Build a $10K Emergency Fund in 6 Months",
                description="Step-by-step savings plan for beginners", keywords=["emergency fund", "savings", "budgeting", "beginner finance"],
                category="budgeting", estimated_search_volume=12000, trend_velocity=0.6, relevance_score=0.85),
            TopicCandidate(brand_id=bid, source_id=sources[0].id, title="5 High-Yield Savings Accounts Compared (2026)",
                description="Data-driven comparison of top HYSA options", keywords=["HYSA", "savings account", "high yield", "comparison"],
                category="banking", estimated_search_volume=28000, trend_velocity=0.75, relevance_score=0.9),
            TopicCandidate(brand_id=bid, source_id=sources[0].id, title="Index Fund vs Individual Stocks: What the Data Says",
                description="Empirical analysis of returns for retail investors", keywords=["investing", "index funds", "stocks", "portfolio"],
                category="investing", estimated_search_volume=45000, trend_velocity=0.5, relevance_score=0.7),
            TopicCandidate(brand_id=bid, source_id=sources[0].id, title="The 50/30/20 Budget Rule is Wrong—Here's What Works",
                description="Contrarian take on popular budgeting advice", keywords=["budget", "50/30/20", "money management", "contrarian"],
                category="budgeting", estimated_search_volume=18000, trend_velocity=0.8, relevance_score=0.88),
            TopicCandidate(brand_id=bid, source_id=sources[0].id, title="How Credit Card Rewards Actually Make You Poorer",
                description="Analysis of credit card reward psychology", keywords=["credit cards", "rewards", "psychology", "spending"],
                category="credit", estimated_search_volume=22000, trend_velocity=0.45, relevance_score=0.65),
            TopicCandidate(brand_id=bid, source_id=sources[0].id, title="Side Hustle Income Tax Guide for 2026",
                description="Tax planning for gig economy workers", keywords=["taxes", "side hustle", "gig economy", "1099"],
                category="taxes", estimated_search_volume=35000, trend_velocity=0.9, relevance_score=0.72),
            TopicCandidate(brand_id=bid, source_id=sources[0].id, title="AI-Powered Budgeting Apps: Which One Actually Works?",
                description="Testing popular AI budgeting tools head-to-head", keywords=["AI", "budgeting app", "fintech", "automation"],
                category="budgeting", estimated_search_volume=15000, trend_velocity=0.85, relevance_score=0.92),
            TopicCandidate(brand_id=bid, source_id=sources[0].id, title="Roth IRA vs Traditional IRA: The Math Nobody Shows You",
                description="Detailed spreadsheet comparison with scenarios", keywords=["IRA", "Roth", "retirement", "tax advantage"],
                category="investing", estimated_search_volume=40000, trend_velocity=0.4, relevance_score=0.75),
        ]
        db.add_all(topics)

        # Trend Signals
        trends = [
            TrendSignal(brand_id=bid, platform="youtube", signal_type="search_trend", keyword="high yield savings account 2026",
                volume=28000, velocity=0.75, strength=SignalStrength.STRONG, is_actionable=True),
            TrendSignal(brand_id=bid, platform="tiktok", signal_type="hashtag_trend", keyword="#budgetingtips",
                volume=150000, velocity=0.85, strength=SignalStrength.STRONG, is_actionable=True),
            TrendSignal(brand_id=bid, platform="youtube", signal_type="search_trend", keyword="side hustle taxes 2026",
                volume=35000, velocity=0.9, strength=SignalStrength.STRONG, is_actionable=True),
            TrendSignal(brand_id=bid, platform="youtube", signal_type="search_trend", keyword="AI budgeting app review",
                volume=15000, velocity=0.85, strength=SignalStrength.STRONG, is_actionable=True),
            TrendSignal(brand_id=bid, platform="instagram", signal_type="engagement_trend", keyword="emergency fund challenge",
                volume=8000, velocity=0.55, strength=SignalStrength.MODERATE, is_actionable=True),
            TrendSignal(brand_id=bid, platform="youtube", signal_type="search_trend", keyword="index fund portfolio 2026",
                volume=45000, velocity=0.5, strength=SignalStrength.MODERATE, is_actionable=True),
            TrendSignal(brand_id=bid, signal_type="general", keyword="credit card rewards trap",
                volume=22000, velocity=0.45, strength=SignalStrength.MODERATE, is_actionable=True),
            TrendSignal(brand_id=bid, signal_type="general", keyword="roth ira vs traditional",
                volume=40000, velocity=0.4, strength=SignalStrength.WEAK, is_actionable=False),
        ]
        db.add_all(trends)

        # Niche Clusters
        niches = [
            NicheCluster(brand_id=bid, cluster_name="budgeting", parent_niche="personal finance",
                keywords=["budget", "savings", "emergency fund", "50/30/20"],
                estimated_audience_size=500000, monetization_potential=0.82, competition_density=0.6,
                content_gap_score=0.55, saturation_level=0.35,
                recommended_entry_angle="Focus on contrarian, data-backed budgeting strategies"),
            NicheCluster(brand_id=bid, cluster_name="investing", parent_niche="personal finance",
                keywords=["index funds", "stocks", "portfolio", "retirement"],
                estimated_audience_size=800000, monetization_potential=0.75, competition_density=0.8,
                content_gap_score=0.3, saturation_level=0.55,
                recommended_entry_angle="Differentiate with accessible data visualizations"),
            NicheCluster(brand_id=bid, cluster_name="banking", parent_niche="personal finance",
                keywords=["HYSA", "savings account", "banking"],
                estimated_audience_size=300000, monetization_potential=0.88, competition_density=0.5,
                content_gap_score=0.65, saturation_level=0.2,
                recommended_entry_angle="High affiliate potential — compare and recommend"),
            NicheCluster(brand_id=bid, cluster_name="taxes", parent_niche="personal finance",
                keywords=["taxes", "1099", "side hustle", "deductions"],
                estimated_audience_size=400000, monetization_potential=0.7, competition_density=0.45,
                content_gap_score=0.6, saturation_level=0.25,
                recommended_entry_angle="Seasonal urgency + practical walkthroughs"),
        ]
        db.add_all(niches)
        db.commit()

        print(f"Phase 2 seed complete for brand '{brand.name}':")
        print(f"  {len(sources)} topic sources")
        print(f"  {len(topics)} topic candidates")
        print(f"  {len(trends)} trend signals")
        print(f"  {len(niches)} niche clusters")
        print(f"  Run scoring: POST /api/v1/brands/{bid}/opportunities/recompute")


if __name__ == "__main__":
    seed()
