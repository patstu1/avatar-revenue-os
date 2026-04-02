"""Affiliate Program API Clients — ClickBank, Amazon Associates, Semrush, Spotify, Target.

Each client handles authentication, offer discovery, and link generation for its network.
"""
from __future__ import annotations
import os
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)
_TIMEOUT = 30.0


def _blocked(msg: str) -> dict[str, Any]:
    return {"success": False, "error": msg, "data": []}


class ClickBankClient:
    """ClickBank Affiliate API — digital product marketplace, high commissions (50-75%)."""

    def __init__(self, api_key: str = "", clerk_id: str = ""):
        self.api_key = api_key or os.environ.get("CLICKBANK_API_KEY", "")
        self.clerk_id = clerk_id or os.environ.get("CLICKBANK_CLERK_ID", "")
        self.base_url = "https://api.clickbank.com/rest/1.3"

    def _is_configured(self) -> bool:
        return bool(self.api_key and self.clerk_id)

    def _headers(self) -> dict:
        return {"Authorization": f"{self.api_key}:{self.clerk_id}", "Accept": "application/json"}

    async def fetch_marketplace(self, category: str = "", sort_by: str = "GRAVITY", max_results: int = 20) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("CLICKBANK_API_KEY / CLICKBANK_CLERK_ID not configured")
        try:
            params: dict[str, Any] = {"sortField": sort_by, "resultsPerPage": max_results}
            if category:
                params["categoryId"] = category
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(f"{self.base_url}/products/list", params=params, headers=self._headers())
                r.raise_for_status()
                return {"success": True, "data": r.json()}
        except Exception as e:
            logger.exception("ClickBank marketplace fetch failed")
            return _blocked(str(e))

    async def fetch_analytics(self, start_date: str, end_date: str) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("CLICKBANK_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(f"{self.base_url}/analytics/status", params={"startDate": start_date, "endDate": end_date}, headers=self._headers())
                r.raise_for_status()
                return {"success": True, "data": r.json()}
        except Exception as e:
            return _blocked(str(e))

    @staticmethod
    def build_hop_link(vendor: str, affiliate_id: str, tracking_id: str = "") -> str:
        url = f"https://{affiliate_id}.{vendor}.hop.clickbank.net"
        if tracking_id:
            url += f"?tid={tracking_id}"
        return url


class AmazonAssociatesClient:
    """Amazon Associates (Product Advertising API 5.0) — massive product catalog, 1-10% commissions."""

    def __init__(self, access_key: str = "", secret_key: str = "", partner_tag: str = ""):
        self.access_key = access_key or os.environ.get("AMAZON_ASSOCIATES_ACCESS_KEY", "")
        self.secret_key = secret_key or os.environ.get("AMAZON_ASSOCIATES_SECRET_KEY", "")
        self.partner_tag = partner_tag or os.environ.get("AMAZON_ASSOCIATES_TAG", "")
        self.base_url = "https://webservices.amazon.com/paapi5"

    def _is_configured(self) -> bool:
        return bool(self.access_key and self.partner_tag)

    async def search_items(self, keywords: str, category: str = "All", max_results: int = 10) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("AMAZON_ASSOCIATES_ACCESS_KEY / AMAZON_ASSOCIATES_TAG not configured")
        try:
            payload = {
                "Keywords": keywords, "SearchIndex": category,
                "ItemCount": max_results, "PartnerTag": self.partner_tag,
                "PartnerType": "Associates", "Resources": ["ItemInfo.Title", "Offers.Listings.Price"],
            }
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.post(f"{self.base_url}/searchitems", json=payload, headers={"Content-Type": "application/json"})
                if r.status_code == 200:
                    return {"success": True, "data": r.json()}
                return _blocked(f"Amazon PA-API HTTP {r.status_code}")
        except Exception as e:
            return _blocked(str(e))

    def build_affiliate_link(self, asin: str) -> str:
        return f"https://www.amazon.com/dp/{asin}?tag={self.partner_tag}"


class SemrushClient:
    """Semrush Affiliate Program (via Impact) — $200 per sale, $10 per trial. High-ticket SaaS."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("SEMRUSH_AFFILIATE_KEY", "")
        self.base_url = "https://www.berush.com/api"

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def fetch_stats(self, start_date: str, end_date: str) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("SEMRUSH_AFFILIATE_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(f"{self.base_url}/stats", params={"key": self.api_key, "dateStart": start_date, "dateEnd": end_date})
                r.raise_for_status()
                return {"success": True, "data": r.json()}
        except Exception as e:
            return _blocked(str(e))

    @staticmethod
    def build_affiliate_link(affiliate_id: str, campaign: str = "") -> str:
        url = f"https://www.semrush.com/?ref={affiliate_id}"
        if campaign:
            url += f"&utm_campaign={campaign}"
        return url


class SpotifyAffiliateClient:
    """Spotify Affiliate (via Impact network) — subscription referrals."""

    def __init__(self):
        self.impact_client = None

    def _is_configured(self) -> bool:
        return bool(os.environ.get("IMPACT_ACCOUNT_SID") and os.environ.get("IMPACT_AUTH_TOKEN"))

    async def fetch_conversions(self, start_date: str, end_date: str) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("Spotify affiliate uses Impact network — set IMPACT_ACCOUNT_SID / IMPACT_AUTH_TOKEN")
        from packages.clients.affiliate_network_clients import ImpactClient
        client = ImpactClient()
        return await client.fetch_conversions(start_date, end_date)

    @staticmethod
    def build_affiliate_link(tracking_id: str = "") -> str:
        base = "https://open.spotify.com/premium"
        if tracking_id:
            base += f"?si={tracking_id}"
        return base


class TargetAffiliateClient:
    """Target Affiliate Program (via Impact/Partnerize) — retail, 1-8% commissions."""

    def __init__(self):
        pass

    def _is_configured(self) -> bool:
        return bool(os.environ.get("IMPACT_ACCOUNT_SID") and os.environ.get("IMPACT_AUTH_TOKEN"))

    async def fetch_conversions(self, start_date: str, end_date: str) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("Target affiliate uses Impact network — set IMPACT_ACCOUNT_SID / IMPACT_AUTH_TOKEN")
        from packages.clients.affiliate_network_clients import ImpactClient
        client = ImpactClient()
        return await client.fetch_conversions(start_date, end_date)

    @staticmethod
    def build_affiliate_link(product_url: str, affiliate_id: str) -> str:
        return f"https://goto.target.com/c/{affiliate_id}?u={product_url}"


class YouTubeShoppingClient:
    """YouTube Shopping — product tagging in videos, Shorts, and live streams."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("GOOGLE_AI_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def get_eligible_products(self, channel_id: str) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("YouTube Shopping requires GOOGLE_AI_API_KEY + YouTube Partner Program")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={"part": "brandingSettings", "id": channel_id, "key": self.api_key},
                )
                return {"success": r.status_code == 200, "data": r.json() if r.status_code == 200 else None}
        except Exception as e:
            return _blocked(str(e))

    @staticmethod
    def build_product_tag(product_url: str, video_id: str) -> dict[str, str]:
        return {"video_id": video_id, "product_url": product_url, "tag_type": "youtube_shopping"}


class TikTokShoppingClient:
    """TikTok Shop — product links in videos and live streams."""

    def __init__(self, access_token: str = ""):
        self.access_token = access_token or os.environ.get("TIKTOK_SHOP_ACCESS_TOKEN", "")
        self.base_url = "https://open-api.tiktokglobalshop.com"

    def _is_configured(self) -> bool:
        return bool(self.access_token)

    async def get_products(self, page_size: int = 20) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("TIKTOK_SHOP_ACCESS_TOKEN not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.post(
                    f"{self.base_url}/api/products/search",
                    json={"page_size": page_size},
                    headers={"x-tts-access-token": self.access_token, "Content-Type": "application/json"},
                )
                return {"success": r.status_code == 200, "data": r.json() if r.status_code == 200 else None}
        except Exception as e:
            return _blocked(str(e))

    @staticmethod
    def build_product_link(product_id: str, affiliate_id: str = "") -> str:
        base = f"https://www.tiktok.com/view/product/{product_id}"
        return f"{base}?affiliate_id={affiliate_id}" if affiliate_id else base


class ShareASaleClient:
    """ShareASale Affiliate Network — 25,000+ merchant programs."""

    def __init__(self, api_token: str = "", api_secret: str = "", affiliate_id: str = ""):
        self.api_token = api_token or os.environ.get("SHAREASALE_API_TOKEN", "")
        self.api_secret = api_secret or os.environ.get("SHAREASALE_API_SECRET", "")
        self.affiliate_id = affiliate_id or os.environ.get("SHAREASALE_AFFILIATE_ID", "")

    def _is_configured(self) -> bool:
        return bool(self.api_token)

    async def fetch_merchants(self, category: str = "") -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("SHAREASALE_API_TOKEN not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                params = {"affiliateId": self.affiliate_id, "token": self.api_token, "version": "2.9", "action": "merchantSearch"}
                if category:
                    params["category"] = category
                r = await client.get("https://api.shareasale.com/x.cfm", params=params)
                return {"success": r.status_code == 200, "data": r.text}
        except Exception as e:
            return _blocked(str(e))

    async def fetch_activity(self, date_start: str, date_end: str) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("SHAREASALE_API_TOKEN not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get("https://api.shareasale.com/x.cfm", params={
                    "affiliateId": self.affiliate_id, "token": self.api_token,
                    "version": "2.9", "action": "activity", "dateStart": date_start, "dateEnd": date_end,
                })
                return {"success": r.status_code == 200, "data": r.text}
        except Exception as e:
            return _blocked(str(e))

    @staticmethod
    def build_affiliate_link(merchant_id: str, affiliate_id: str, destination_url: str = "") -> str:
        base = f"https://www.shareasale.com/r.cfm?b=&u={affiliate_id}&m={merchant_id}"
        if destination_url:
            base += f"&urllink={destination_url}"
        return base


class ImpactClient:
    """Impact.com Affiliate Network — enterprise affiliate platform."""

    def __init__(self, account_sid: str = "", auth_token: str = ""):
        self.account_sid = account_sid or os.environ.get("IMPACT_ACCOUNT_SID", "")
        self.auth_token = auth_token or os.environ.get("IMPACT_AUTH_TOKEN", "")

    def _is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token)

    async def fetch_campaigns(self) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("IMPACT_ACCOUNT_SID / IMPACT_AUTH_TOKEN not configured")
        try:
            import base64
            creds = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(
                    f"https://api.impact.com/Advertisers/{self.account_sid}/Campaigns",
                    headers={"Authorization": f"Basic {creds}", "Accept": "application/json"},
                )
                return {"success": r.status_code == 200, "data": r.json() if r.status_code == 200 else None}
        except Exception as e:
            return _blocked(str(e))

    @staticmethod
    def build_tracking_link(campaign_id: str, affiliate_id: str, destination_url: str = "") -> str:
        return f"https://impact.com/c/{affiliate_id}/{campaign_id}?u={destination_url}"


class EtsyAffiliateClient:
    """Etsy Affiliate Program (via Awin) — handmade/vintage marketplace, 4% commission."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("ETSY_AFFILIATE_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def search_listings(self, keywords: str, limit: int = 10) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("ETSY_AFFILIATE_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(
                    "https://openapi.etsy.com/v3/application/listings/active",
                    params={"keywords": keywords, "limit": limit},
                    headers={"x-api-key": self.api_key},
                )
                return {"success": r.status_code == 200, "data": r.json() if r.status_code == 200 else None}
        except Exception as e:
            return _blocked(str(e))

    @staticmethod
    def build_affiliate_link(listing_url: str, affiliate_id: str) -> str:
        return f"https://www.awin1.com/cread.php?awinmid=6220&awinaffid={affiliate_id}&ued={listing_url}"


class WPXHostingClient:
    """WPX Hosting Affiliate — premium WordPress hosting, $100+ per sale."""

    def __init__(self):
        pass

    def _is_configured(self) -> bool:
        return True

    @staticmethod
    def build_affiliate_link(affiliate_id: str, campaign: str = "") -> str:
        url = f"https://wpx.net/?affid={affiliate_id}"
        if campaign:
            url += f"&utm_campaign={campaign}"
        return url


AFFILIATE_PROGRAMS: dict[str, dict[str, Any]] = {
    "clickbank": {
        "name": "ClickBank",
        "type": "digital_marketplace",
        "commission_range": "50-75%",
        "cookie_days": 60,
        "best_niches": ["make_money_online", "health_fitness", "self_improvement", "education_courses", "personal_finance", "crypto", "real_estate"],
        "env_keys": ["CLICKBANK_API_KEY", "CLICKBANK_CLERK_ID"],
        "payout_model": "percentage",
        "avg_payout": 40.0,
    },
    "amazon": {
        "name": "Amazon Associates",
        "type": "retail_marketplace",
        "commission_range": "1-10%",
        "cookie_days": 1,
        "best_niches": ["tech_reviews", "cooking_recipes", "beauty_skincare", "gaming", "health_fitness", "personal_finance", "self_improvement", "travel"],
        "env_keys": ["AMAZON_ASSOCIATES_ACCESS_KEY", "AMAZON_ASSOCIATES_TAG"],
        "payout_model": "percentage",
        "avg_payout": 5.0,
    },
    "semrush": {
        "name": "Semrush",
        "type": "saas_high_ticket",
        "commission_range": "$200/sale, $10/trial",
        "cookie_days": 120,
        "best_niches": ["business_entrepreneurship", "software_saas", "make_money_online", "ai_tools", "personal_finance"],
        "env_keys": ["SEMRUSH_AFFILIATE_KEY"],
        "payout_model": "flat",
        "avg_payout": 200.0,
    },
    "spotify": {
        "name": "Spotify",
        "type": "subscription_referral",
        "commission_range": "varies",
        "cookie_days": 14,
        "best_niches": ["self_improvement", "health_fitness", "cooking_recipes", "travel"],
        "env_keys": ["IMPACT_ACCOUNT_SID", "IMPACT_AUTH_TOKEN"],
        "payout_model": "flat",
        "avg_payout": 5.0,
    },
    "target": {
        "name": "Target",
        "type": "retail",
        "commission_range": "1-8%",
        "cookie_days": 7,
        "best_niches": ["cooking_recipes", "beauty_skincare", "health_fitness", "tech_reviews"],
        "env_keys": ["IMPACT_ACCOUNT_SID", "IMPACT_AUTH_TOKEN"],
        "payout_model": "percentage",
        "avg_payout": 8.0,
    },
    "youtube_shopping": {
        "name": "YouTube Shopping",
        "type": "platform_commerce",
        "commission_range": "varies by merchant",
        "cookie_days": 0,
        "best_niches": ["tech_reviews", "beauty_skincare", "cooking_recipes", "health_fitness", "gaming"],
        "env_keys": ["GOOGLE_AI_API_KEY"],
        "payout_model": "percentage",
        "avg_payout": 10.0,
    },
    "tiktok_shopping": {
        "name": "TikTok Shop",
        "type": "platform_commerce",
        "commission_range": "5-20%",
        "cookie_days": 0,
        "best_niches": ["beauty_skincare", "health_fitness", "cooking_recipes", "tech_reviews", "self_improvement"],
        "env_keys": ["TIKTOK_SHOP_ACCESS_TOKEN"],
        "payout_model": "percentage",
        "avg_payout": 12.0,
    },
    "shareasale": {
        "name": "ShareASale",
        "type": "affiliate_network",
        "commission_range": "varies (5-50%)",
        "cookie_days": 30,
        "best_niches": ["business_entrepreneurship", "software_saas", "health_fitness", "beauty_skincare", "personal_finance", "make_money_online", "education_courses"],
        "env_keys": ["SHAREASALE_API_TOKEN"],
        "payout_model": "mixed",
        "avg_payout": 25.0,
    },
    "impact": {
        "name": "Impact",
        "type": "affiliate_network",
        "commission_range": "varies by advertiser",
        "cookie_days": 30,
        "best_niches": ["software_saas", "business_entrepreneurship", "personal_finance", "tech_reviews", "travel", "health_fitness"],
        "env_keys": ["IMPACT_ACCOUNT_SID", "IMPACT_AUTH_TOKEN"],
        "payout_model": "mixed",
        "avg_payout": 30.0,
    },
    "etsy": {
        "name": "Etsy",
        "type": "marketplace",
        "commission_range": "4%",
        "cookie_days": 30,
        "best_niches": ["beauty_skincare", "cooking_recipes", "self_improvement", "travel"],
        "env_keys": ["ETSY_AFFILIATE_API_KEY"],
        "payout_model": "percentage",
        "avg_payout": 4.0,
    },
    "wpx": {
        "name": "WPX Hosting",
        "type": "saas_high_ticket",
        "commission_range": "$100+ per sale",
        "cookie_days": 60,
        "best_niches": ["software_saas", "business_entrepreneurship", "make_money_online", "ai_tools"],
        "env_keys": [],
        "payout_model": "flat",
        "avg_payout": 100.0,
    },
}


def get_best_programs_for_niche(niche: str, require_configured: bool = False) -> list[dict[str, Any]]:
    """Return affiliate programs ranked by fit for a given niche."""
    matches = []
    for key, prog in AFFILIATE_PROGRAMS.items():
        if niche in prog["best_niches"]:
            configured = all(os.environ.get(k) for k in prog["env_keys"])
            if require_configured and not configured:
                continue
            matches.append({**prog, "program_key": key, "configured": configured})
    matches.sort(key=lambda x: x["avg_payout"], reverse=True)
    return matches


def get_all_configured_programs() -> list[dict[str, Any]]:
    """Return all affiliate programs that have credentials configured."""
    configured = []
    for key, prog in AFFILIATE_PROGRAMS.items():
        if all(os.environ.get(k) for k in prog["env_keys"]):
            configured.append({**prog, "program_key": key, "configured": True})
    return configured
