"""Affiliate Network API Clients — Impact, ShareASale, CJ, Amazon Associates.

Each client handles authentication, data fetching, and tracked link generation.
"""

from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0


def _blocked(msg: str) -> dict[str, Any]:
    return {"success": False, "error": msg, "data": []}


# ── Amazon Associates ────────────────────────────────────────────────


class AmazonAssociatesLinkGenerator:
    """Generate tracked Amazon affiliate links.

    Format: https://www.amazon.com/dp/{asin}?tag={associate_tag}
    Supports custom sub-tags for content-level attribution.
    """

    def __init__(self, associate_tag: str = ""):
        self.associate_tag = associate_tag or os.environ.get("AMAZON_ASSOCIATES_TAG", "")

    def generate_product_link(
        self,
        asin: str,
        *,
        associate_tag: str = "",
        sub_tag: str = "",
    ) -> dict[str, Any]:
        """Generate a tracked Amazon product link.

        Args:
            asin: Amazon Standard Identification Number.
            associate_tag: Override the default associate tag.
            sub_tag: Optional sub-tag for content-level attribution.

        Returns:
            dict with tracked_url, network, asin, tag.
        """
        tag = associate_tag or self.associate_tag
        if not tag:
            return _blocked("AMAZON_ASSOCIATES_TAG not configured")

        url = f"https://www.amazon.com/dp/{asin}?tag={tag}"
        if sub_tag:
            url += f"&ascsubtag={sub_tag}"

        return {
            "success": True,
            "tracked_url": url,
            "network": "amazon",
            "asin": asin,
            "tag": tag,
        }

    def generate_search_link(
        self,
        keywords: str,
        *,
        associate_tag: str = "",
        category: str = "",
    ) -> dict[str, Any]:
        """Generate a tracked Amazon search link."""
        tag = associate_tag or self.associate_tag
        if not tag:
            return _blocked("AMAZON_ASSOCIATES_TAG not configured")

        encoded_kw = quote_plus(keywords)
        url = f"https://www.amazon.com/s?k={encoded_kw}&tag={tag}"
        if category:
            url += f"&i={quote_plus(category)}"

        return {"success": True, "tracked_url": url, "network": "amazon", "tag": tag}


# ── Impact ───────────────────────────────────────────────────────────


class ImpactClient:
    """Impact.com Affiliate Network API client."""

    def __init__(self, account_sid: str = "", auth_token: str = ""):
        self.account_sid = account_sid or os.environ.get("IMPACT_ACCOUNT_SID", "")
        self.auth_token = auth_token or os.environ.get("IMPACT_AUTH_TOKEN", "")
        self.base_url = f"https://api.impact.com/Advertisers/{self.account_sid}"

    def _headers(self) -> dict:
        import base64

        creds = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
        return {"Authorization": f"Basic {creds}", "Accept": "application/json"}

    async def fetch_conversions(self, start_date: str, end_date: str) -> dict[str, Any]:
        if not self.account_sid or not self.auth_token:
            return _blocked("IMPACT_ACCOUNT_SID / IMPACT_AUTH_TOKEN not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(
                    f"{self.base_url}/Actions",
                    params={"StartDate": start_date, "EndDate": end_date, "PageSize": 100},
                    headers=self._headers(),
                )
                r.raise_for_status()
                return {"success": True, "data": r.json().get("Actions", [])}
        except Exception as e:
            logger.exception("Impact fetch_conversions failed")
            return _blocked(str(e))

    async def fetch_offers(self) -> dict[str, Any]:
        if not self.account_sid or not self.auth_token:
            return _blocked("IMPACT_ACCOUNT_SID / IMPACT_AUTH_TOKEN not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(f"{self.base_url}/Campaigns", headers=self._headers())
                r.raise_for_status()
                return {"success": True, "data": r.json().get("Campaigns", [])}
        except Exception as e:
            logger.exception("Impact fetch_offers failed")
            return _blocked(str(e))

    async def fetch_campaigns(self) -> dict[str, Any]:
        """Alias for fetch_offers — returns campaign listings."""
        return await self.fetch_offers()

    @staticmethod
    def build_tracking_link(campaign_id: str, affiliate_id: str, destination_url: str = "") -> str:
        return f"https://impact.com/c/{affiliate_id}/{campaign_id}?u={destination_url}"

    async def create_tracking_link(
        self,
        campaign_id: str,
        destination_url: str,
        *,
        sub_id_1: str = "",
        sub_id_2: str = "",
        shared_id: str = "",
    ) -> dict[str, Any]:
        """Create a tracked link via the Impact Tracking Link API.

        Uses the Impact /Campaigns/{campaignId}/TrackingLinks endpoint to generate
        a real tracked link with optional sub-IDs for content-level attribution.
        Falls back to URL construction if the API call fails.
        """
        if not self.account_sid or not self.auth_token:
            # Fallback to static construction
            url = self.build_tracking_link(campaign_id, self.account_sid, destination_url)
            return {"success": True, "tracked_url": url, "network": "impact", "method": "constructed"}

        try:
            payload: dict[str, Any] = {
                "CampaignId": campaign_id,
                "Url": destination_url,
            }
            if sub_id_1:
                payload["SubId1"] = sub_id_1
            if sub_id_2:
                payload["SubId2"] = sub_id_2
            if shared_id:
                payload["SharedId"] = shared_id

            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.post(
                    f"{self.base_url}/Campaigns/{campaign_id}/TrackingLinks",
                    json=payload,
                    headers=self._headers(),
                )
                if r.status_code in (200, 201):
                    data = r.json()
                    tracked_url = data.get("TrackingLink", data.get("Url", ""))
                    return {
                        "success": True,
                        "tracked_url": tracked_url,
                        "network": "impact",
                        "campaign_id": campaign_id,
                        "method": "api",
                        "data": data,
                    }
                # API returned non-success — fall back to constructed link
                fallback = self.build_tracking_link(campaign_id, self.account_sid, destination_url)
                return {
                    "success": True,
                    "tracked_url": fallback,
                    "network": "impact",
                    "method": "constructed_fallback",
                    "api_status": r.status_code,
                }
        except Exception as e:
            logger.warning("Impact create_tracking_link API failed, using fallback", error=str(e))
            fallback = self.build_tracking_link(campaign_id, self.account_sid, destination_url)
            return {"success": True, "tracked_url": fallback, "network": "impact", "method": "constructed_fallback"}


# ── ShareASale ───────────────────────────────────────────────────────


class ShareASaleClient:
    """ShareASale Affiliate Network API client."""

    def __init__(self, api_token: str = "", api_secret: str = "", merchant_id: str = ""):
        self.api_token = api_token or os.environ.get("SHAREASALE_API_TOKEN", "")
        self.api_secret = api_secret or os.environ.get("SHAREASALE_API_SECRET", "")
        self.merchant_id = merchant_id or os.environ.get("SHAREASALE_MERCHANT_ID", "")
        self.base_url = "https://api.shareasale.com/x.cfm"

    async def fetch_activity(self, date_start: str, date_end: str) -> dict[str, Any]:
        if not self.api_token or not self.api_secret:
            return _blocked("SHAREASALE_API_TOKEN / SHAREASALE_API_SECRET not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(
                    self.base_url,
                    params={
                        "affiliateId": self.merchant_id,
                        "token": self.api_token,
                        "version": "2.9",
                        "action": "activity",
                        "dateStart": date_start,
                        "dateEnd": date_end,
                        "XMLFormat": "1",
                    },
                )
                r.raise_for_status()
                return {"success": True, "data": r.text}
        except Exception as e:
            logger.exception("ShareASale fetch_activity failed")
            return _blocked(str(e))

    async def fetch_merchants(self, category: str = "") -> dict[str, Any]:
        if not self.api_token:
            return _blocked("SHAREASALE_API_TOKEN not configured")
        try:
            params: dict[str, Any] = {
                "affiliateId": self.merchant_id,
                "token": self.api_token,
                "version": "2.9",
                "action": "merchantSearch",
            }
            if category:
                params["category"] = category
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(self.base_url, params=params)
                r.raise_for_status()
                return {"success": True, "data": r.text}
        except Exception as e:
            logger.exception("ShareASale fetch_merchants failed")
            return _blocked(str(e))

    @staticmethod
    def build_affiliate_link(merchant_id: str, affiliate_id: str, destination_url: str = "") -> str:
        base = f"https://www.shareasale.com/r.cfm?b=&u={affiliate_id}&m={merchant_id}"
        if destination_url:
            base += f"&urllink={destination_url}"
        return base

    def create_custom_link(
        self,
        destination_url: str,
        *,
        affiliate_id: str = "",
        merchant_id: str = "",
        tracking_id: str = "",
    ) -> dict[str, Any]:
        """Create a tracked ShareASale custom link.

        ShareASale custom links use URL construction (no async API needed).
        Format: https://www.shareasale.com/r.cfm?b=&u={affiliate_id}&m={merchant_id}&urllink={url}
        """
        aff_id = affiliate_id or self.merchant_id
        merch_id = merchant_id or self.merchant_id
        if not aff_id:
            return _blocked("SHAREASALE_MERCHANT_ID / affiliate_id not configured")

        encoded_dest = quote_plus(destination_url)
        url = f"https://www.shareasale.com/r.cfm?b=&u={aff_id}&m={merch_id}&urllink={encoded_dest}"
        if tracking_id:
            url += f"&afftrack={tracking_id}"

        return {
            "success": True,
            "tracked_url": url,
            "network": "shareasale",
            "affiliate_id": aff_id,
            "merchant_id": merch_id,
        }


# ── CJ (Commission Junction) ────────────────────────────────────────


class CJClient:
    """CJ Affiliate (Commission Junction) API client."""

    def __init__(self, api_key: str = "", website_id: str = ""):
        self.api_key = api_key or os.environ.get("CJ_API_KEY", "")
        self.website_id = website_id or os.environ.get("CJ_WEBSITE_ID", "")
        self.base_url = "https://commissions.api.cj.com/query"
        self.link_api_url = "https://link-search.api.cj.com/v2/link-search"

    async def fetch_commissions(self, start_date: str, end_date: str) -> dict[str, Any]:
        if not self.api_key:
            return _blocked("CJ_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(
                    self.base_url,
                    params={"date-type": "event", "start-date": start_date, "end-date": end_date},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                r.raise_for_status()
                return {"success": True, "data": r.json()}
        except Exception as e:
            logger.exception("CJ fetch_commissions failed")
            return _blocked(str(e))

    def create_link(
        self,
        advertiser_id: str,
        destination_url: str,
        *,
        website_id: str = "",
        sid: str = "",
    ) -> dict[str, Any]:
        """Create a tracked CJ deep link.

        CJ deep links use the format:
        https://www.anrdoezrs.net/links/{website_id}/type/dlg/{advertiser_id}?url={destination}
        SID (Shopper ID) provides content-level attribution.
        """
        wid = website_id or self.website_id
        if not wid:
            return _blocked("CJ_WEBSITE_ID not configured")

        encoded_dest = quote_plus(destination_url)
        url = f"https://www.anrdoezrs.net/links/{wid}/type/dlg/{advertiser_id}?url={encoded_dest}"
        if sid:
            url += f"&sid={sid}"

        return {
            "success": True,
            "tracked_url": url,
            "network": "cj",
            "website_id": wid,
            "advertiser_id": advertiser_id,
        }

    async def search_links(
        self,
        advertiser_id: str,
        *,
        keywords: str = "",
        link_type: str = "Text Link",
    ) -> dict[str, Any]:
        """Search for existing CJ advertiser links."""
        if not self.api_key:
            return _blocked("CJ_API_KEY not configured")
        try:
            params: dict[str, Any] = {
                "website-id": self.website_id,
                "advertiser-ids": advertiser_id,
                "link-type": link_type,
            }
            if keywords:
                params["keywords"] = keywords
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(
                    self.link_api_url,
                    params=params,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                r.raise_for_status()
                return {"success": True, "data": r.json()}
        except Exception as e:
            logger.exception("CJ search_links failed")
            return _blocked(str(e))
