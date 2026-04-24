"""YouTube Analytics sync service — pulls channel stats via YouTube Data API v3."""
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.publishing import PerformanceMetric
from packages.db.enums import Platform

logger = logging.getLogger(__name__)

YT_API_BASE = "https://www.googleapis.com/youtube/v3"
_TIMEOUT = httpx.Timeout(30.0)


async def sync_youtube_account(db: AsyncSession, account: CreatorAccount) -> dict[str, Any]:
    """Sync YouTube channel statistics for a single account.

    Uses the stored platform_access_token as the OAuth bearer token (or API key).
    """
    token = account.platform_access_token
    if not token:
        return {"account_id": str(account.id), "status": "no_credentials", "metrics_synced": 0}

    headers = {"Authorization": f"Bearer {token}"}
    metrics_synced = 0

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            channel_data = await _fetch_channel_stats(client, headers, account.platform_external_id)
            if not channel_data:
                return {"account_id": str(account.id), "status": "channel_not_found", "metrics_synced": 0}

            account.follower_count = channel_data.get("subscriber_count", account.follower_count)
            account.platform_external_id = account.platform_external_id or channel_data.get("channel_id", "")

            videos = await _fetch_recent_videos(client, headers, channel_data["channel_id"])

            for video in videos:
                stats = await _fetch_video_stats(client, headers, video["id"])
                if not stats:
                    continue

                existing = (await db.execute(
                    select(PerformanceMetric).where(
                        PerformanceMetric.creator_account_id == account.id,
                        PerformanceMetric.raw_data["youtube_video_id"].astext == video["id"],
                    )
                )).scalar_one_or_none()

                if existing:
                    existing.views = stats.get("views", existing.views)
                    existing.likes = stats.get("likes", existing.likes)
                    existing.comments = stats.get("comments", existing.comments)
                    existing.measured_at = datetime.now(timezone.utc)
                    existing.raw_data = {**(existing.raw_data or {}), **stats, "youtube_video_id": video["id"]}
                else:
                    pm = PerformanceMetric(
                        content_item_id=None,
                        creator_account_id=account.id,
                        brand_id=account.brand_id,
                        platform=Platform.YOUTUBE,
                        impressions=0,
                        views=stats.get("views", 0),
                        likes=stats.get("likes", 0),
                        comments=stats.get("comments", 0),
                        shares=0,
                        saves=stats.get("favorites", 0),
                        clicks=0,
                        ctr=0.0,
                        watch_time_seconds=0,
                        avg_watch_pct=0.0,
                        followers_gained=0,
                        revenue=0.0,
                        revenue_source="youtube",
                        rpm=0.0,
                        engagement_rate=_calc_engagement(stats),
                        raw_data={"youtube_video_id": video["id"], **stats, "title": video.get("title", "")},
                    )
                    db.add(pm)
                metrics_synced += 1

            account.last_synced_at = datetime.now(timezone.utc)
            await db.flush()

    except httpx.HTTPError as e:
        logger.warning("YouTube API error for account %s: %s", account.id, e)
        return {"account_id": str(account.id), "status": "api_error", "error": str(e), "metrics_synced": 0}
    except Exception as e:
        logger.exception("YouTube sync failed for account %s", account.id)
        return {"account_id": str(account.id), "status": "error", "error": str(e), "metrics_synced": 0}

    return {
        "account_id": str(account.id),
        "platform": "youtube",
        "status": "completed",
        "metrics_synced": metrics_synced,
        "subscriber_count": channel_data.get("subscriber_count", 0),
        "video_count": channel_data.get("video_count", 0),
    }


async def _fetch_channel_stats(client: httpx.AsyncClient, headers: dict, channel_id: str | None) -> dict | None:
    params: dict[str, str] = {"part": "statistics,snippet"}
    if channel_id:
        params["id"] = channel_id
    else:
        params["mine"] = "true"

    resp = await client.get(f"{YT_API_BASE}/channels", params=params, headers=headers)
    if resp.status_code != 200:
        logger.warning("YouTube channels API returned %d: %s", resp.status_code, resp.text[:200])
        return None

    items = resp.json().get("items", [])
    if not items:
        return None

    ch = items[0]
    stats = ch.get("statistics", {})
    return {
        "channel_id": ch["id"],
        "title": ch.get("snippet", {}).get("title", ""),
        "subscriber_count": int(stats.get("subscriberCount", 0)),
        "video_count": int(stats.get("videoCount", 0)),
        "view_count": int(stats.get("viewCount", 0)),
    }


async def _fetch_recent_videos(client: httpx.AsyncClient, headers: dict, channel_id: str, max_results: int = 20) -> list[dict]:
    params = {
        "part": "snippet",
        "channelId": channel_id,
        "order": "date",
        "maxResults": str(max_results),
        "type": "video",
    }
    resp = await client.get(f"{YT_API_BASE}/search", params=params, headers=headers)
    if resp.status_code != 200:
        return []

    videos = []
    for item in resp.json().get("items", []):
        vid_id = item.get("id", {}).get("videoId")
        if vid_id:
            videos.append({
                "id": vid_id,
                "title": item.get("snippet", {}).get("title", ""),
            })
    return videos


async def _fetch_video_stats(client: httpx.AsyncClient, headers: dict, video_id: str) -> dict | None:
    resp = await client.get(
        f"{YT_API_BASE}/videos",
        params={"part": "statistics", "id": video_id},
        headers=headers,
    )
    if resp.status_code != 200:
        return None

    items = resp.json().get("items", [])
    if not items:
        return None

    stats = items[0].get("statistics", {})
    return {
        "views": int(stats.get("viewCount", 0)),
        "likes": int(stats.get("likeCount", 0)),
        "comments": int(stats.get("commentCount", 0)),
        "favorites": int(stats.get("favoriteCount", 0)),
    }


def _calc_engagement(stats: dict) -> float:
    views = stats.get("views", 0)
    if views == 0:
        return 0.0
    engagement = stats.get("likes", 0) + stats.get("comments", 0)
    return round(engagement / views * 100, 4)
