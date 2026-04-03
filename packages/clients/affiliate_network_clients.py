"""Affiliate Network API Clients — Impact, ShareASale, CJ."""
from __future__ import annotations
import os
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0


def _blocked(msg: str) -> dict[str, Any]:
    return {"success": False, "error": msg, "data": []}


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
                r = await client.get(f"{self.base_url}/Actions", params={"StartDate": start_date, "EndDate": end_date, "PageSize": 100}, headers=self._headers())
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
                r = await client.get(self.base_url, params={
                    "affiliateId": self.merchant_id, "token": self.api_token,
                    "version": "2.9", "action": "activity", "dateStart": date_start, "dateEnd": date_end,
                    "XMLFormat": "1",
                })
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
                "affiliateId": self.merchant_id, "token": self.api_token,
                "version": "2.9", "action": "merchantSearch",
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


class CJClient:
    """CJ Affiliate (Commission Junction) API client."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("CJ_API_KEY", "")
        self.base_url = "https://commissions.api.cj.com/query"

    async def fetch_commissions(self, start_date: str, end_date: str) -> dict[str, Any]:
        if not self.api_key:
            return _blocked("CJ_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(self.base_url, params={"date-type": "event", "start-date": start_date, "end-date": end_date}, headers={"Authorization": f"Bearer {self.api_key}"})
                r.raise_for_status()
                return {"success": True, "data": r.json()}
        except Exception as e:
            logger.exception("CJ fetch_commissions failed")
            return _blocked(str(e))
