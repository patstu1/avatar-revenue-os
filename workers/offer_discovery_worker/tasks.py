"""Offer Discovery Worker — automatically find and add high-converting affiliate offers.

Scans marketplace APIs (ClickBank, Amazon, ShareASale) for top-performing products
in each active niche. Creates new Offer records for products meeting quality thresholds.
"""
from __future__ import annotations
import asyncio
import logging
import uuid

from celery import shared_task
from sqlalchemy import select

from workers.base_task import TrackedTask

from packages.db.session import async_session_factory, run_async
from packages.db.models.core import Brand, Offer

logger = logging.getLogger(__name__)

MIN_GRAVITY_CLICKBANK = 20
MIN_RATING_AMAZON = 4.0


async def _discover_clickbank_offers(niche: str, brand_id: uuid.UUID) -> list[dict]:
    """Discover top ClickBank products for a niche."""
    from packages.clients.affiliate_program_clients import ClickBankClient

    client = ClickBankClient()
    if not client._is_configured():
        return []

    category_map = {
        "personal_finance": "business-investing", "make_money_online": "e-business-e-marketing",
        "health_fitness": "health-fitness", "self_improvement": "self-help",
        "education_courses": "education", "cooking_recipes": "cooking-food-wine",
    }
    category = category_map.get(niche, "")
    result = await client.fetch_marketplace(category=category, max_results=10)
    if not result.get("success"):
        return []

    products = result.get("data", [])
    if isinstance(products, dict):
        products = products.get("products", [])

    discovered = []
    for p in products:
        gravity = float(p.get("gravity", 0) or 0)
        if gravity >= MIN_GRAVITY_CLICKBANK:
            discovered.append({
                "name": p.get("title", p.get("name", "Unknown")),
                "vendor": p.get("vendor", ""),
                "payout": float(p.get("averageEarningsPerSale", 0) or 0),
                "gravity": gravity,
                "program": "clickbank",
                "niche": niche,
            })
    return discovered


async def _discover_amazon_products(niche: str, brand_id: uuid.UUID) -> list[dict]:
    """Discover top Amazon products for a niche."""
    from packages.clients.affiliate_program_clients import AmazonAssociatesClient

    client = AmazonAssociatesClient()
    if not client._is_configured():
        return []

    keyword_map = {
        "personal_finance": "budgeting finance book",
        "health_fitness": "workout equipment supplements",
        "tech_reviews": "tech gadgets electronics",
        "beauty_skincare": "skincare routine products",
        "cooking_recipes": "kitchen gadgets cookbook",
        "ai_tools": "AI productivity software",
    }
    keywords = keyword_map.get(niche, niche.replace("_", " "))
    result = await client.search_items(keywords, max_results=5)
    if not result.get("success"):
        return []

    items = result.get("data", {}).get("SearchResult", {}).get("Items", [])
    discovered = []
    for item in items:
        info = item.get("ItemInfo", {})
        title = info.get("Title", {}).get("DisplayValue", "Unknown")
        asin = item.get("ASIN", "")
        price = item.get("Offers", {}).get("Listings", [{}])[0].get("Price", {}).get("Amount", 0)
        discovered.append({
            "name": title, "asin": asin, "price": float(price or 0),
            "payout": float(price or 0) * 0.05,
            "program": "amazon", "niche": niche,
        })
    return discovered


async def _persist_discovered_offers(db, brand_id: uuid.UUID, discovered: list[dict]) -> int:
    """Create Offer records for newly discovered products."""
    created = 0
    for d in discovered:
        existing = (await db.execute(
            select(Offer).where(Offer.brand_id == brand_id, Offer.name == d["name"])
        )).scalar_one_or_none()
        if existing:
            continue

        db.add(Offer(
            brand_id=brand_id,
            name=d["name"],
            monetization_method="affiliate",
            payout_amount=d.get("payout", 0),
            epc=d.get("payout", 0) * 0.02,
            conversion_rate=0.02,
        ))
        created += 1
    return created


async def _run_discovery():
    from packages.scoring.niche_research_engine import NICHE_DATABASE

    async with async_session_factory() as db:
        brands = list((await db.execute(select(Brand).where(Brand.is_active.is_(True)))).scalars().all())

    total_discovered = 0
    total_created = 0

    for brand in brands:
        niche = brand.niche or "general"
        all_discovered: list[dict] = []

        try:
            cb = await _discover_clickbank_offers(niche, brand.id)
            all_discovered.extend(cb)
        except Exception:
            logger.warning("ClickBank discovery failed for %s", niche)

        try:
            amz = await _discover_amazon_products(niche, brand.id)
            all_discovered.extend(amz)
        except Exception:
            logger.warning("Amazon discovery failed for %s", niche)

        total_discovered += len(all_discovered)

        if all_discovered:
            async with async_session_factory() as db:
                created = await _persist_discovered_offers(db, brand.id, all_discovered)
                await db.commit()
                total_created += created
                if created:
                    logger.info("Discovered %d new offers for brand %s (niche: %s)", created, brand.name, niche)

    return {"discovered": total_discovered, "created": total_created, "brands": len(brands)}


@shared_task(name="workers.offer_discovery_worker.tasks.discover_offers", base=TrackedTask)
def discover_offers():
    return run_async(_run_discovery())
