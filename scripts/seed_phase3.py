"""Phase 3 seed: content items for QA/approval/publish testing.
Run: docker exec aro-api python scripts/seed_phase3.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.db.enums import ContentType
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentBrief, ContentItem, Script
from packages.db.models.core import Brand
from packages.db.models.offers import Offer
from packages.db.session import get_sync_engine

engine = get_sync_engine()


def seed():
    with Session(engine) as db:
        brand = db.execute(select(Brand).limit(1)).scalar_one_or_none()
        if not brand:
            print("No brands. Run seed.py first.")
            return

        existing = db.query(ContentItem).filter(ContentItem.brand_id == brand.id).first()
        if existing:
            print("Phase 3 already seeded. Skipping.")
            return

        bid = brand.id
        offer = db.execute(select(Offer).where(Offer.brand_id == bid).limit(1)).scalar_one_or_none()
        account = db.execute(select(CreatorAccount).where(CreatorAccount.brand_id == bid).limit(1)).scalar_one_or_none()
        brief = db.execute(select(ContentBrief).where(ContentBrief.brand_id == bid).limit(1)).scalar_one_or_none()

        if not brief:
            brief = ContentBrief(
                brand_id=bid, title="Seed Brief: 5 Budget Hacks",
                content_type=ContentType.SHORT_VIDEO, target_platform="youtube",
                hook="Stop wasting money on subscriptions you forgot about",
                angle="Contrarian budgeting",
                key_points=["Track spending", "Cancel unused subs", "Automate savings"],
                cta_strategy="Link to budget app in description",
                status="script_generated",
            )
            db.add(brief)
            db.flush()

        script = db.execute(select(Script).where(Script.brand_id == bid).limit(1)).scalar_one_or_none()
        if not script:
            script = Script(
                brief_id=brief.id, brand_id=bid, version=1,
                title="5 Budget Hacks Script",
                hook_text="Stop wasting money on subscriptions you forgot about",
                body_text="Today we break down the 5 budget hacks that actually work...",
                cta_text="Check the link in the description for the best budget app",
                full_script="[HOOK]\nStop wasting money...\n\n[BODY]\n5 hacks...\n\n[CTA]\nCheck the link",
                word_count=45, generation_model="template_v1", status="generated",
            )
            db.add(script)
            db.flush()

        items = [
            ContentItem(
                brand_id=bid, brief_id=brief.id, script_id=script.id,
                creator_account_id=account.id if account else None,
                title="5 Budget Hacks That Actually Work",
                description="Data-driven budgeting tips for beginners",
                content_type=ContentType.SHORT_VIDEO, platform="youtube",
                tags=["budget", "money", "finance", "tips", "savings"],
                hashtags=["#budgeting", "#moneytips", "#finance2026"],
                status="draft",
                monetization_method="affiliate",
                offer_id=offer.id if offer else None,
                total_cost=3.50,
            ),
            ContentItem(
                brand_id=bid, brief_id=brief.id,
                title="High-Yield Savings Account Comparison",
                content_type=ContentType.SHORT_VIDEO, platform="youtube",
                tags=["HYSA", "savings", "banking", "comparison"],
                status="qa_complete",
                monetization_method="affiliate",
                offer_id=offer.id if offer else None,
                total_cost=2.80,
            ),
            ContentItem(
                brand_id=bid,
                title="Credit Card Rewards Deep Dive",
                content_type=ContentType.SHORT_VIDEO, platform="tiktok",
                tags=["credit cards", "rewards", "points"],
                status="approved",
                monetization_method="affiliate",
                total_cost=1.90,
            ),
        ]
        db.add_all(items)
        db.commit()
        print(f"Phase 3 seed complete: {len(items)} content items created")


if __name__ == "__main__":
    seed()
