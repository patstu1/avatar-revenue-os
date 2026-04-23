"""Platform Analytics & Affiliate Commission Clients.

Ingests real performance data from YouTube, TikTok, Instagram,
and affiliate commission data from Amazon Associates and Impact.

When credentials are not configured, each client returns a structured
`{"configured": False}` response so the system can fall back gracefully.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger()


class YouTubeAnalyticsClient:
    """Fetches video performance data from YouTube Analytics API v2."""

    BASE_URL = "https://youtubeanalytics.googleapis.com/v2/reports"

    def __init__(self, api_key: str | None = None, oauth_token: str | None = None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY", "")
        self.oauth_token = oauth_token or os.getenv("YOUTUBE_OAUTH_TOKEN", "")
        if not api_key and (self.api_key or self.oauth_token):
            logger.warning("credential_env_fallback_DEPRECATED", client="YouTubeAnalyticsClient",
                           hint="Pass api_key from integration_manager.get_credential()")

    def is_configured(self) -> bool:
        return bool(self.api_key or self.oauth_token)

    async def fetch_video_metrics(
        self, channel_id: str, *, days: int = 7,
    ) -> dict:
        """Fetch views, watch time, likes, comments, shares, revenue for a channel."""
        if not self.is_configured():
            return {"configured": False, "error": "YOUTUBE_API_KEY or YOUTUBE_OAUTH_TOKEN not set"}

        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                headers = {"Authorization": f"Bearer {self.oauth_token}"} if self.oauth_token else {}
                params = {
                    "ids": f"channel=={channel_id}",
                    "startDate": start_date,
                    "endDate": end_date,
                    "metrics": "views,estimatedMinutesWatched,likes,comments,shares,estimatedRevenue,subscribersGained",
                    "dimensions": "video",
                    "sort": "-views",
                    "maxResults": 50,
                }
                if self.api_key and not self.oauth_token:
                    params["key"] = self.api_key

                resp = await client.get(self.BASE_URL, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()

                rows = data.get("rows", [])
                columns = data.get("columnHeaders", [])
                col_names = [c.get("name", "") for c in columns]

                results = []
                for row in rows:
                    entry = dict(zip(col_names, row))
                    results.append(entry)

                return {"configured": True, "channel_id": channel_id, "period_days": days,
                        "video_count": len(results), "metrics": results}

        except Exception as e:
            logger.error("youtube_analytics.fetch_failed", channel_id=channel_id, error=str(e))
            return {"configured": True, "error": str(e), "metrics": []}


class TikTokAnalyticsClient:
    """Fetches video performance data from TikTok Research API."""

    BASE_URL = "https://open.tiktokapis.com/v2"

    def __init__(self, access_token: str | None = None):
        self.access_token = access_token or os.getenv("TIKTOK_ACCESS_TOKEN", "")
        if not access_token and self.access_token:
            logger.warning("credential_env_fallback_DEPRECATED", client="TikTokAnalyticsClient",
                           hint="Pass access_token from integration_manager.get_credential()")

    def is_configured(self) -> bool:
        return bool(self.access_token)

    async def fetch_video_metrics(
        self, username: str, *, days: int = 7,
    ) -> dict:
        """Fetch views, likes, comments, shares for recent videos."""
        if not self.is_configured():
            return {"configured": False, "error": "TIKTOK_ACCESS_TOKEN not set"}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                headers = {"Authorization": f"Bearer {self.access_token}",
                            "Content-Type": "application/json"}

                # Fetch user videos
                resp = await client.post(
                    f"{self.BASE_URL}/video/list/",
                    headers=headers,
                    json={"max_count": 20,
                          "fields": ["id", "create_time", "like_count", "comment_count",
                                     "share_count", "view_count", "duration"]},
                )
                resp.raise_for_status()
                data = resp.json()
                videos = data.get("data", {}).get("videos", [])

                return {"configured": True, "username": username, "period_days": days,
                        "video_count": len(videos), "metrics": videos}

        except Exception as e:
            logger.error("tiktok_analytics.fetch_failed", username=username, error=str(e))
            return {"configured": True, "error": str(e), "metrics": []}


class InstagramAnalyticsClient:
    """Fetches media insights from Instagram Graph API."""

    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, access_token: str | None = None):
        self.access_token = access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
        if not access_token and self.access_token:
            logger.warning("credential_env_fallback_DEPRECATED", client="InstagramAnalyticsClient",
                           hint="Pass access_token from integration_manager.get_credential()")

    def is_configured(self) -> bool:
        return bool(self.access_token)

    async def fetch_media_insights(
        self, ig_user_id: str, *, limit: int = 20,
    ) -> dict:
        """Fetch impressions, reach, engagement for recent media."""
        if not self.is_configured():
            return {"configured": False, "error": "INSTAGRAM_ACCESS_TOKEN not set"}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/{ig_user_id}/media",
                    params={"access_token": self.access_token,
                            "fields": "id,caption,media_type,timestamp,like_count,comments_count",
                            "limit": limit},
                )
                resp.raise_for_status()
                data = resp.json()
                media = data.get("data", [])

                return {"configured": True, "user_id": ig_user_id,
                        "media_count": len(media), "metrics": media}

        except Exception as e:
            logger.error("instagram_analytics.fetch_failed", user_id=ig_user_id, error=str(e))
            return {"configured": True, "error": str(e), "metrics": []}


class TrendSignalClient:
    """Fetches trending topics from Google Trends and social platforms."""

    TRENDS_URL = "https://serpapi.com/search"  # SerpAPI for Google Trends (requires key)

    def __init__(self, serp_key: str | None = None, rapid_key: str | None = None):
        self.serp_key = serp_key or os.getenv("SERPAPI_KEY", "")
        self.rapid_key = rapid_key or os.getenv("RAPIDAPI_KEY", "")
        if not serp_key and (self.serp_key or self.rapid_key):
            logger.warning("credential_env_fallback_DEPRECATED", client="TrendSignalClient",
                           hint="Pass serp_key from integration_manager.get_credential()")

    def is_configured(self) -> bool:
        return bool(self.serp_key or self.rapid_key)

    async def fetch_trending_topics(
        self, *, geo: str = "US", category: str = "all",
    ) -> dict:
        """Fetch current trending topics from Google Trends."""
        if not self.is_configured():
            return {"configured": False, "error": "SERPAPI_KEY or RAPIDAPI_KEY not set"}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if self.serp_key:
                    resp = await client.get(self.TRENDS_URL, params={
                        "engine": "google_trends_trending_now",
                        "geo": geo, "api_key": self.serp_key,
                    })
                    resp.raise_for_status()
                    data = resp.json()
                    trends = data.get("trending_searches", [])
                    return {"configured": True, "source": "google_trends",
                            "geo": geo, "trend_count": len(trends), "trends": trends[:50]}

            return {"configured": True, "trends": [], "error": "no supported API key"}

        except Exception as e:
            logger.error("trend_signal.fetch_failed", error=str(e))
            return {"configured": True, "error": str(e), "trends": []}

    async def fetch_youtube_trending(self, *, region: str = "US", youtube_api_key: str | None = None) -> dict:
        """Fetch YouTube trending videos for topic discovery."""
        api_key = youtube_api_key or os.getenv("YOUTUBE_API_KEY", "")
        if not api_key:
            return {"configured": False, "error": "YOUTUBE_API_KEY not set"}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={"part": "snippet,statistics", "chart": "mostPopular",
                            "regionCode": region, "maxResults": 50, "key": api_key},
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])
                topics = [{"title": v["snippet"]["title"],
                            "channel": v["snippet"]["channelTitle"],
                            "views": int(v["statistics"].get("viewCount", 0)),
                            "category": v["snippet"].get("categoryId")}
                           for v in items]
                return {"configured": True, "source": "youtube_trending",
                        "video_count": len(topics), "topics": topics}

        except Exception as e:
            logger.error("youtube_trending.fetch_failed", error=str(e))
            return {"configured": True, "error": str(e), "topics": []}


# ── Affiliate Commission Sync Clients ────────────────────────────────


class AmazonAssociatesClient:
    """Fetch earnings reports from Amazon Product Advertising API 5.0.

    Uses the PA-API GetEarnings endpoint to pull commission data
    for a configured Associates tag.
    """

    BASE_URL = "https://webservices.amazon.com/paapi5/getitems"
    EARNINGS_URL = "https://affiliate-program.amazon.com/home/reports/api/data"

    def __init__(
        self,
        access_key: str | None = None,
        secret_key: str | None = None,
        partner_tag: str | None = None,
    ):
        self.access_key = access_key or os.getenv("AMAZON_ASSOCIATES_ACCESS_KEY", "")
        self.secret_key = secret_key or os.getenv("AMAZON_ASSOCIATES_SECRET_KEY", "")
        self.partner_tag = partner_tag or os.getenv("AMAZON_ASSOCIATES_TAG", "")
        if not access_key and (self.access_key or self.partner_tag):
            logger.warning(
                "credential_env_fallback_DEPRECATED",
                client="AmazonAssociatesClient",
                hint="Pass credentials from integration_manager.get_credential()",
            )

    def is_configured(self) -> bool:
        return bool(self.access_key and self.secret_key and self.partner_tag)

    async def fetch_earnings(self, *, days: int = 7) -> dict:
        """Fetch recent earnings/commissions from Amazon Associates reporting API.

        Returns list of commission events with: order_id, items_shipped,
        revenue, ad_fees (commissions), clicks, conversion_rate, date.
        """
        if not self.is_configured():
            return {"configured": False, "error": "AMAZON_ASSOCIATES keys not set"}

        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Amazon Associates Reporting API (requires signed request)
                # Uses the summary earnings endpoint
                resp = await client.get(
                    self.EARNINGS_URL,
                    params={
                        "startDate": start_date,
                        "endDate": end_date,
                        "tag": self.partner_tag,
                        "groupBy": "day",
                    },
                    headers={
                        "x-amz-access-key": self.access_key,
                        "x-amz-secret-key": self.secret_key,
                        "Accept": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                reports = data.get("data", data.get("reports", []))

                commissions = []
                for entry in reports:
                    commissions.append({
                        "date": entry.get("date", ""),
                        "clicks": int(entry.get("clicks", 0)),
                        "items_ordered": int(entry.get("items_ordered", entry.get("orderedItems", 0))),
                        "items_shipped": int(entry.get("items_shipped", entry.get("shippedItems", 0))),
                        "revenue": float(entry.get("revenue", entry.get("shippedRevenue", 0))),
                        "ad_fees": float(entry.get("ad_fees", entry.get("totalEarnings", 0))),
                        "conversion_rate": float(entry.get("conversion_rate", entry.get("conversionRate", 0))),
                        "tag": self.partner_tag,
                    })

                return {
                    "configured": True,
                    "network": "amazon_associates",
                    "partner_tag": self.partner_tag,
                    "period_days": days,
                    "commission_count": len(commissions),
                    "commissions": commissions,
                }

        except Exception as e:
            logger.error("amazon_associates.fetch_failed", error=str(e))
            return {"configured": True, "error": str(e), "commissions": []}


class ImpactCommissionClient:
    """Fetch commission/action data from Impact (formerly Impact Radius) API.

    Uses the Impact Partner API to pull conversion actions and commissions.
    Docs: https://developer.impact.com/default#operations-Actions-ListActions
    """

    BASE_URL = "https://api.impact.com"

    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
    ):
        self.account_sid = account_sid or os.getenv("IMPACT_ACCOUNT_SID", "")
        self.auth_token = auth_token or os.getenv("IMPACT_AUTH_TOKEN", "")
        if not account_sid and (self.account_sid or self.auth_token):
            logger.warning(
                "credential_env_fallback_DEPRECATED",
                client="ImpactCommissionClient",
                hint="Pass credentials from integration_manager.get_credential()",
            )

    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token)

    async def fetch_actions(self, *, days: int = 7) -> dict:
        """Fetch recent conversion actions (commissions) from Impact.

        Returns list of actions with: action_id, action_date, ad_id,
        campaign_name, payout, status, customer_status, etc.
        """
        if not self.is_configured():
            return {"configured": False, "error": "IMPACT credentials not set"}

        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:59Z")
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/Mediapartners/{self.account_sid}/Actions",
                    params={
                        "StartDate": start_date,
                        "EndDate": end_date,
                        "PageSize": 100,
                    },
                    auth=(self.account_sid, self.auth_token),
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
                actions_raw = data.get("Actions", [])

                commissions = []
                for a in actions_raw:
                    commissions.append({
                        "action_id": a.get("Id", ""),
                        "action_date": a.get("EventDate", a.get("ActionDate", "")),
                        "campaign_id": a.get("CampaignId", ""),
                        "campaign_name": a.get("CampaignName", ""),
                        "ad_id": a.get("AdId", ""),
                        "payout": float(a.get("Payout", 0)),
                        "sale_amount": float(a.get("Amount", a.get("SaleAmount", 0))),
                        "status": a.get("State", a.get("Status", "unknown")),
                        "customer_status": a.get("CustomerStatus", ""),
                        "sub_id_1": a.get("SharedId", a.get("SubId1", "")),
                        "sub_id_2": a.get("SubId2", ""),
                    })

                return {
                    "configured": True,
                    "network": "impact",
                    "account_sid": self.account_sid,
                    "period_days": days,
                    "commission_count": len(commissions),
                    "commissions": commissions,
                }

        except Exception as e:
            logger.error("impact.fetch_failed", error=str(e))
            return {"configured": True, "error": str(e), "commissions": []}
