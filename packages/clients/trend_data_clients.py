"""Trend Data Source Clients — YouTube, Google Trends, TikTok, Reddit.

Each client fetches trending/rising data and returns normalized results.

Credentials are passed in by the calling worker via credential_loader.
No os.environ fallback — dashboard/provider config is the source of truth.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)
_TIMEOUT = 30.0


def _blocked(msg: str) -> dict[str, Any]:
    return {"success": False, "error": msg, "data": []}


class YouTubeTrendingClient:
    """Fetch trending videos and search trends from YouTube Data API v3."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"

    async def fetch_trending(self, region: str = "US", category_id: str = "0", max_results: int = 25) -> dict[str, Any]:
        if not self.api_key:
            return _blocked("GOOGLE_AI_API_KEY not configured (YouTube Data API shares this key)")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(f"{self.base_url}/videos", params={
                    "part": "snippet,statistics", "chart": "mostPopular",
                    "regionCode": region, "videoCategoryId": category_id,
                    "maxResults": max_results, "key": self.api_key,
                })
                r.raise_for_status()
                items = r.json().get("items", [])
                return {"success": True, "data": [
                    {
                        "source": "youtube_trending", "title": i["snippet"]["title"],
                        "channel": i["snippet"].get("channelTitle", ""),
                        "category_id": i["snippet"].get("categoryId", ""),
                        "views": int(i["statistics"].get("viewCount", 0)),
                        "likes": int(i["statistics"].get("likeCount", 0)),
                        "comments": int(i["statistics"].get("commentCount", 0)),
                        "published_at": i["snippet"].get("publishedAt", ""),
                        "video_id": i["id"],
                        "tags": i["snippet"].get("tags", [])[:10],
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    }
                    for i in items
                ]}
        except Exception as e:
            logger.exception("YouTube trending fetch failed")
            return _blocked(str(e))

    async def search_trending_topics(self, query: str, max_results: int = 10) -> dict[str, Any]:
        if not self.api_key:
            return _blocked("GOOGLE_AI_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(f"{self.base_url}/search", params={
                    "part": "snippet", "q": query, "type": "video",
                    "order": "viewCount", "publishedAfter": "2026-03-01T00:00:00Z",
                    "maxResults": max_results, "key": self.api_key,
                })
                r.raise_for_status()
                items = r.json().get("items", [])
                return {"success": True, "data": [
                    {
                        "source": "youtube_search", "title": i["snippet"]["title"],
                        "channel": i["snippet"].get("channelTitle", ""),
                        "video_id": i["id"].get("videoId", ""),
                        "description": i["snippet"].get("description", "")[:200],
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    }
                    for i in items
                ]}
        except Exception as e:
            logger.exception("YouTube search failed")
            return _blocked(str(e))


class GoogleTrendsClient:
    """Fetch rising search trends from Google Trends (via unofficial API)."""

    async def fetch_daily_trends(self, geo: str = "US") -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(
                    "https://trends.google.com/trends/api/dailytrends",
                    params={"hl": "en-US", "tz": "-300", "geo": geo, "ns": "15"},
                )
                text = r.text
                if text.startswith(")]}'"):
                    text = text[5:]
                import json
                data = json.loads(text)
                trends = data.get("default", {}).get("trendingSearchesDays", [])
                results = []
                for day in trends:
                    for t in day.get("trendingSearches", []):
                        results.append({
                            "source": "google_trends",
                            "title": t.get("title", {}).get("query", ""),
                            "traffic": t.get("formattedTraffic", ""),
                            "related_queries": [rq.get("query", "") for rq in t.get("relatedQueries", [])[:5]],
                            "articles": [a.get("title", "") for a in t.get("articles", [])[:3]],
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        })
                return {"success": True, "data": results}
        except Exception as e:
            logger.exception("Google Trends fetch failed")
            return _blocked(str(e))


class RedditTrendingClient:
    """Fetch rising posts from Reddit (no API key needed for public JSON)."""

    async def fetch_rising(self, subreddit: str = "popular", limit: int = 15) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": "AvatarRevenueOS/1.0"}) as client:
                r = await client.get(f"https://www.reddit.com/r/{subreddit}/rising.json", params={"limit": limit})
                r.raise_for_status()
                posts = r.json().get("data", {}).get("children", [])
                return {"success": True, "data": [
                    {
                        "source": "reddit_rising",
                        "title": p["data"]["title"],
                        "subreddit": p["data"]["subreddit"],
                        "score": p["data"]["score"],
                        "num_comments": p["data"]["num_comments"],
                        "url": p["data"]["url"],
                        "created_utc": p["data"]["created_utc"],
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    }
                    for p in posts
                ]}
        except Exception as e:
            logger.exception("Reddit rising fetch failed")
            return _blocked(str(e))

    async def fetch_niche_trends(self, niche_subreddits: list[str], limit: int = 100) -> dict[str, Any]:
        all_posts = []
        for sub in niche_subreddits:
            result = await self.fetch_rising(sub, limit)
            if result.get("success"):
                all_posts.extend(result["data"])
        all_posts.sort(key=lambda x: x.get("score", 0), reverse=True)
        return {"success": True, "data": all_posts}


class TikTokTrendClient:
    """Fetch trending hashtags/sounds from TikTok Creative Center (public endpoints)."""

    async def fetch_trending_hashtags(self, country: str = "US") -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(
                    "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list",
                    params={"page": 1, "limit": 20, "period": 7, "country_code": country},
                )
                if r.status_code == 200:
                    data = r.json()
                    items = data.get("data", {}).get("list", [])
                    return {"success": True, "data": [
                        {
                            "source": "tiktok_hashtag",
                            "hashtag": h.get("hashtag_name", ""),
                            "video_count": h.get("video_count", 0),
                            "view_count": h.get("view_count", 0),
                            "trend_type": h.get("trend_type", ""),
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        }
                        for h in items
                    ]}
                return _blocked(f"TikTok Creative Center returned {r.status_code}")
        except Exception as e:
            logger.exception("TikTok trend fetch failed")
            return _blocked(str(e))
