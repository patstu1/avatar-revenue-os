#!/usr/bin/env python3
"""Seed the B2B package ladder into the offers system.

Creates 6 packages for each of 3 brands:
  - Aesthetic Theory (beauty)
  - Body Theory (fitness)
  - Tool Signal (SaaS/AI)

Usage:
  docker-compose exec api python scripts/seed_packages.py
  # or locally:
  DATABASE_URL_SYNC=postgresql://... python scripts/seed_packages.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# ── Package definitions ──────────────────────────────────────────────

PACKAGES = [
    {
        "slug": "ugc-starter-pack",
        "name": "UGC Starter Pack",
        "price": 1500,
        "payout_type": "fixed",
        "monetization_method": "CONSULTING",
        "description": "Fast-turn UGC-style creative for brands that need usable content now.",
        "deliverables": "4 short-form video assets, 3 hook variations, 1 CTA angle, light editing, 7-day turnaround",
    },
    {
        "slug": "growth-content-pack",
        "name": "Growth Content Pack",
        "price": 2500,
        "payout_type": "fixed",
        "monetization_method": "CONSULTING",
        "description": "A monthly content engine for brands that need more assets, more hooks, and more consistency.",
        "deliverables": "8-12 short-form assets/month, multiple hook/caption variations, 2 CTA angles, monthly creative refresh",
    },
    {
        "slug": "performance-creative-pack",
        "name": "Performance Creative Pack",
        "price": 4500,
        "payout_type": "fixed",
        "monetization_method": "CONSULTING",
        "description": "Creative built for testing, iteration, and stronger performance.",
        "deliverables": "12-20 short-form assets/month, hook/angle testing variations, offer/landing support, monthly optimization, creative reporting",
    },
    {
        "slug": "full-creative-retainer",
        "name": "Full Creative Retainer",
        "price": 7500,
        "payout_type": "fixed",
        "monetization_method": "CONSULTING",
        "description": "A full creative retainer for brands that need serious output and ongoing support.",
        "deliverables": "Recurring production, multi-angle hooks, offer/landing support, reporting/strategy, priority turnaround",
    },
    {
        "slug": "creative-strategy-funnel-upgrade",
        "name": "Creative Strategy / Funnel Upgrade",
        "price": 2500,
        "payout_type": "fixed",
        "monetization_method": "CONSULTING",
        "description": "Sharpen the message, strengthen the offer, and improve the path from content to conversion.",
        "deliverables": "Messaging refinement, offer positioning review, landing/funnel upgrade recommendations, content-to-CTA alignment",
    },
    {
        "slug": "launch-sprint",
        "name": "Launch Sprint",
        "price": 5000,
        "payout_type": "fixed",
        "monetization_method": "CONSULTING",
        "description": "A fast-turn sprint for launches, pushes, and urgent campaign windows.",
        "deliverables": "Fast-turn asset batch, launch-focused hook set, CTA alignment, compressed timeline, campaign-ready package",
    },
]

BRANDS = [
    {"slug": "aesthetic-theory", "name": "Aesthetic Theory", "niche": "beauty", "sub_niche": "skincare and aesthetics"},
    {"slug": "body-theory", "name": "Body Theory", "niche": "fitness", "sub_niche": "fitness and wellness"},
    {"slug": "tool-signal", "name": "Tool Signal", "niche": "saas", "sub_niche": "AI and software"},
]


def main():
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    db_url = os.environ.get("DATABASE_URL_SYNC", "")
    if not db_url:
        print("ERROR: DATABASE_URL_SYNC not set")
        sys.exit(1)

    engine = create_engine(db_url)

    with Session(engine) as session:
        from packages.db.models.core import Brand, Organization
        from packages.db.models.offers import Offer

        # Get or create org
        org = session.execute(
            select(Organization).where(Organization.is_active.is_(True)).limit(1)
        ).scalar_one_or_none()
        if not org:
            org = Organization(name="ProofHook", slug="proofhook", is_active=True)
            session.add(org)
            session.flush()
            print(f"Created org: {org.name} ({org.id})")

        offers_created = 0
        brands_created = 0

        for brand_def in BRANDS:
            brand = session.execute(select(Brand).where(Brand.slug == brand_def["slug"])).scalar_one_or_none()

            if not brand:
                brand = Brand(
                    organization_id=org.id,
                    name=brand_def["name"],
                    slug=brand_def["slug"],
                    niche=brand_def["niche"],
                    sub_niche=brand_def["sub_niche"],
                    is_active=True,
                    decision_mode="guarded_auto",
                )
                session.add(brand)
                session.flush()
                brands_created += 1
                print(f"Created brand: {brand.name} ({brand.id})")
            else:
                print(f"Brand exists: {brand.name} ({brand.id})")

            for pkg in PACKAGES:
                offer_name = f"{pkg['name']} — {brand_def['name']}"
                existing = session.execute(
                    select(Offer).where(Offer.brand_id == brand.id, Offer.name == offer_name)
                ).scalar_one_or_none()

                if existing:
                    print(f"  Offer exists: {offer_name}")
                    continue

                offer = Offer(
                    brand_id=brand.id,
                    name=offer_name,
                    description=pkg["description"],
                    monetization_method=pkg["monetization_method"],
                    payout_amount=pkg["price"],
                    payout_type=pkg["payout_type"],
                    offer_url=f"/offers/{brand_def['slug']}/{pkg['slug']}",
                    cta_template=f"Book your {pkg['name']} now — {{url}}",
                    rotation_weight=1.0,
                    is_active=True,
                    priority=PACKAGES.index(pkg),
                )
                session.add(offer)
                offers_created += 1
                print(f"  Created offer: {offer_name} (${pkg['price']})")

        session.commit()

    print(f"\nDone! Brands created: {brands_created}, Offers created: {offers_created}")


if __name__ == "__main__":
    main()
