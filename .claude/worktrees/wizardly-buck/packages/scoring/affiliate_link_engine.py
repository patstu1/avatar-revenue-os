"""Affiliate Link Engine — auto-generate real tracked affiliate links per content piece.

Builds network-specific links (ClickBank hop, Amazon tag+ASIN, Semrush ref, ShareASale deep, etc.)
with per-content tracking IDs for attribution.
"""
from __future__ import annotations
import hashlib
import os
from typing import Any, Optional


def generate_tracking_id(content_item_id: str, account_id: str = "", platform: str = "") -> str:
    """Generate a unique tracking ID for affiliate attribution."""
    raw = f"{content_item_id}:{account_id}:{platform}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def build_clickbank_link(vendor: str, tracking_id: str = "") -> str:
    affiliate_id = os.environ.get("CLICKBANK_CLERK_ID", "")
    if not affiliate_id:
        return ""
    url = f"https://{affiliate_id}.{vendor}.hop.clickbank.net"
    if tracking_id:
        url += f"?tid={tracking_id}"
    return url


def build_amazon_link(asin: str, tracking_id: str = "") -> str:
    tag = os.environ.get("AMAZON_ASSOCIATES_TAG", "")
    if not tag:
        return ""
    url = f"https://www.amazon.com/dp/{asin}?tag={tag}"
    if tracking_id:
        url += f"&linkCode=ll1&ref_={tracking_id}"
    return url


def build_semrush_link(tracking_id: str = "", campaign: str = "") -> str:
    ref_id = os.environ.get("SEMRUSH_AFFILIATE_KEY", "")
    if not ref_id:
        return ""
    url = f"https://www.semrush.com/?ref={ref_id}"
    if campaign:
        url += f"&utm_campaign={campaign}"
    if tracking_id:
        url += f"&utm_content={tracking_id}"
    return url


def build_shareasale_link(merchant_id: str, destination_url: str = "", tracking_id: str = "") -> str:
    aff_id = os.environ.get("SHAREASALE_AFFILIATE_ID", "")
    if not aff_id:
        return ""
    url = f"https://www.shareasale.com/r.cfm?b=&u={aff_id}&m={merchant_id}"
    if destination_url:
        url += f"&urllink={destination_url}"
    if tracking_id:
        url += f"&afftrack={tracking_id}"
    return url


def build_impact_link(campaign_id: str, destination_url: str = "", tracking_id: str = "") -> str:
    aff_id = os.environ.get("IMPACT_ACCOUNT_SID", "")
    if not aff_id:
        return ""
    url = f"https://goto.target.com/c/{aff_id}/{campaign_id}"
    if destination_url:
        url += f"?u={destination_url}"
    if tracking_id:
        url += f"&subId1={tracking_id}"
    return url


def build_etsy_link(listing_url: str, tracking_id: str = "") -> str:
    aff_id = os.environ.get("ETSY_AFFILIATE_API_KEY", "")
    if not aff_id:
        return ""
    url = f"https://www.awin1.com/cread.php?awinmid=6220&awinaffid={aff_id}&ued={listing_url}"
    if tracking_id:
        url += f"&clickref={tracking_id}"
    return url


def build_wpx_link(tracking_id: str = "") -> str:
    url = "https://wpx.net/?affid=affiliate"
    if tracking_id:
        url += f"&utm_content={tracking_id}"
    return url


NICHE_TOP_PRODUCTS: dict[str, list[dict[str, Any]]] = {
    "personal_finance": [
        {"program": "clickbank", "vendor": "monesave", "name": "Money Saving Blueprint", "payout": 35},
        {"program": "semrush", "name": "Semrush SEO Suite", "payout": 200},
        {"program": "amazon", "asin": "B0BX7MVNM4", "name": "Rich Dad Poor Dad", "payout": 1.5},
        {"program": "amazon", "asin": "B09MYFJK4L", "name": "Budgeting Planner", "payout": 2.0},
    ],
    "make_money_online": [
        {"program": "clickbank", "vendor": "cbuniv", "name": "ClickBank University", "payout": 47},
        {"program": "semrush", "name": "Semrush", "payout": 200},
        {"program": "wpx", "name": "WPX Hosting", "payout": 100},
        {"program": "amazon", "asin": "B08N5WRWNW", "name": "Laptop for Business", "payout": 15},
    ],
    "health_fitness": [
        {"program": "clickbank", "vendor": "leanbely", "name": "Lean Belly Breakthrough", "payout": 30},
        {"program": "amazon", "asin": "B001GAOTSW", "name": "Optimum Nutrition Whey", "payout": 3},
        {"program": "amazon", "asin": "B07D9FXDM4", "name": "Resistance Bands Set", "payout": 2},
        {"program": "clickbank", "vendor": "metaboost", "name": "MetaBoost Connection", "payout": 40},
    ],
    "tech_reviews": [
        {"program": "amazon", "asin": "B0BSHF7WHW", "name": "MacBook Air M3", "payout": 50},
        {"program": "amazon", "asin": "B0C8R5PF8L", "name": "iPhone 16 Pro", "payout": 40},
        {"program": "amazon", "asin": "B0D1XD1ZV3", "name": "Sony WH-1000XM5", "payout": 15},
        {"program": "semrush", "name": "Semrush", "payout": 200},
    ],
    "ai_tools": [
        {"program": "semrush", "name": "Semrush", "payout": 200},
        {"program": "wpx", "name": "WPX Hosting", "payout": 100},
        {"program": "clickbank", "vendor": "aicash", "name": "AI Cash Machine", "payout": 37},
        {"program": "amazon", "asin": "B0BTK13PC9", "name": "AI Superpowers Book", "payout": 1.5},
    ],
    "crypto": [
        {"program": "clickbank", "vendor": "btcprofit", "name": "Bitcoin Profit Secrets", "payout": 45},
        {"program": "amazon", "asin": "B07BPP2LYM", "name": "Mastering Bitcoin", "payout": 2},
    ],
    "beauty_skincare": [
        {"program": "amazon", "asin": "B00TTD9BRC", "name": "CeraVe Moisturizer", "payout": 1.5},
        {"program": "amazon", "asin": "B004Y9GZRI", "name": "Neutrogena Sunscreen", "payout": 1},
        {"program": "clickbank", "vendor": "skinbright", "name": "Skin Brightening Formula", "payout": 25},
    ],
    "software_saas": [
        {"program": "semrush", "name": "Semrush", "payout": 200},
        {"program": "wpx", "name": "WPX Hosting", "payout": 100},
        {"program": "shareasale", "merchant_id": "46191", "name": "ConvertKit", "payout": 30},
    ],
    "business_entrepreneurship": [
        {"program": "semrush", "name": "Semrush", "payout": 200},
        {"program": "clickbank", "vendor": "cbuniv", "name": "ClickBank University", "payout": 47},
        {"program": "wpx", "name": "WPX Hosting", "payout": 100},
    ],
    "self_improvement": [
        {"program": "clickbank", "vendor": "manifpower", "name": "Manifestation Program", "payout": 35},
        {"program": "amazon", "asin": "B01H4G2J1U", "name": "Atomic Habits", "payout": 1.5},
    ],
    "cooking_recipes": [
        {"program": "amazon", "asin": "B00FLYWNYQ", "name": "Instant Pot", "payout": 5},
        {"program": "amazon", "asin": "B07FZ8S74R", "name": "Lodge Cast Iron", "payout": 2},
    ],
}


def select_best_product(niche: str, content_title: str = "", tracking_id: str = "") -> dict[str, Any]:
    """Select the best specific product for a niche and build its tracked link."""
    products = NICHE_TOP_PRODUCTS.get(niche, [])
    if not products:
        products = NICHE_TOP_PRODUCTS.get("make_money_online", [])

    products_sorted = sorted(products, key=lambda p: p.get("payout", 0), reverse=True)

    for product in products_sorted:
        link = _build_link_for_product(product, tracking_id)
        if link:
            return {
                "name": product["name"],
                "program": product["program"],
                "payout": product.get("payout", 0),
                "link": link,
                "tracking_id": tracking_id,
            }

    for product in products_sorted:
        return {
            "name": product["name"],
            "program": product["program"],
            "payout": product.get("payout", 0),
            "link": "",
            "tracking_id": tracking_id,
            "needs_credentials": True,
        }

    return {"name": "", "program": "", "payout": 0, "link": "", "tracking_id": tracking_id}


def _build_link_for_product(product: dict, tracking_id: str) -> str:
    prog = product.get("program", "")
    if prog == "clickbank":
        return build_clickbank_link(product.get("vendor", ""), tracking_id)
    elif prog == "amazon":
        return build_amazon_link(product.get("asin", ""), tracking_id)
    elif prog == "semrush":
        return build_semrush_link(tracking_id, campaign=product.get("name", "").replace(" ", "_").lower())
    elif prog == "shareasale":
        return build_shareasale_link(product.get("merchant_id", ""), tracking_id=tracking_id)
    elif prog == "wpx":
        return build_wpx_link(tracking_id)
    elif prog == "etsy":
        return build_etsy_link(product.get("listing_url", ""), tracking_id)
    return ""


def get_all_products_for_niche(niche: str) -> list[dict[str, Any]]:
    """Get all available products for a niche, sorted by payout."""
    products = NICHE_TOP_PRODUCTS.get(niche, [])
    return sorted(products, key=lambda p: p.get("payout", 0), reverse=True)
