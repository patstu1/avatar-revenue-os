"""Platform Analytics Clients — ingests real performance data from YouTube, TikTok, Instagram.

These clients fetch actual views, engagement, revenue, and subscriber data
from platform APIs. They require OAuth credentials to activate.

Credentials are passed in by the calling worker via credential_loader.
No os.environ fallback — dashboard/provider config is the source of truth.

When credentials are not configured, each client returns a structured
`{"configured": False}` response so the system can fall back gracefully.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger()


class YouTubeAnalyticsClient:
    """Fetches video performance data from YouTube Analytics API v2."""

    BASE_URL = "https://youtubeanalytics.googleapis.com/v2/reports"

    def __init__(self, api_key: str | None = None, oauth_token: str | None = None):
        self.api_key = api_key or ""
        self.oauth_token = oauth_token or ""

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
        self.access_token = access_token or ""

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
        self.access_token = access_token or ""

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
        self.serp_key = serp_key or ""
        self.rapid_key = rapid_key or ""

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
        api_key = youtube_api_key or ""
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
