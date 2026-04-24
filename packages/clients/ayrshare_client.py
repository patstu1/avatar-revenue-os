"""Ayrshare API client — social media distribution.

Ayrshare supports: YouTube, TikTok, Instagram, X, LinkedIn, Reddit, Pinterest, Facebook, Telegram.
API docs: https://docs.ayrshare.com
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _blocked(msg: str) -> dict[str, Any]:
    return {"success": False, "blocked": True, "error": msg, "data": None}


def _fail(msg: str, status_code: int = 0) -> dict[str, Any]:
    return {"success": False, "blocked": False, "error": msg, "data": None, "status_code": status_code}


class AyrshareClient:
    """Real HTTP client for Ayrshare's REST API (v2)."""

    BASE_URL = "https://app.ayrshare.com/api"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("AYRSHARE_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def get_profiles(self) -> dict[str, Any]:
        """List connected social profiles (user endpoint)."""
        if not self._is_configured():
            return _blocked("AYRSHARE_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(f"{self.BASE_URL}/user", headers=self._headers())
            if resp.status_code != 200:
                return _fail(f"Ayrshare profiles HTTP {resp.status_code}", resp.status_code)
            data = resp.json()
            profiles = data.get("activeSocialAccounts", [])
            return {"success": True, "blocked": False, "data": profiles, "status_code": resp.status_code, "error": None}
        except httpx.HTTPError as e:
            logger.error("ayrshare.network_error", error=str(e))
            return _fail(f"Ayrshare network error: {e}")

    async def create_post(
        self,
        platforms: list[str],
        text: str,
        *,
        media_urls: list[str] | None = None,
        link_url: str | None = None,
        scheduled_date: str | None = None,
        shorten_links: bool = True,
    ) -> dict[str, Any]:
        """Post to one or more platforms simultaneously.

        platforms: list of platform names e.g. ["twitter", "instagram", "linkedin", "tiktok", "reddit", "youtube"]
        """
        if not self._is_configured():
            return _blocked("AYRSHARE_API_KEY not configured")

        payload: dict[str, Any] = {
            "post": text,
            "platforms": platforms,
            "shortenLinks": shorten_links,
        }
        if media_urls:
            payload["mediaUrls"] = media_urls
        if link_url:
            payload["mediaUrls"] = payload.get("mediaUrls", []) + [link_url]
        if scheduled_date:
            payload["scheduleDate"] = scheduled_date

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(f"{self.BASE_URL}/post", json=payload, headers=self._headers())
            if resp.status_code not in (200, 201):
                return _fail(f"Ayrshare post HTTP {resp.status_code}: {resp.text[:200]}", resp.status_code)
            return {"success": True, "blocked": False, "data": resp.json(), "status_code": resp.status_code, "error": None}
        except httpx.HTTPError as e:
            logger.error("ayrshare.create_post_error", error=str(e))
            return _fail(f"Ayrshare network error: {e}")

    async def get_post(self, post_id: str) -> dict[str, Any]:
        """Get status of a post by ID."""
        if not self._is_configured():
            return _blocked("AYRSHARE_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(f"{self.BASE_URL}/post/{post_id}", headers=self._headers())
            if resp.status_code != 200:
                return _fail(f"Ayrshare get_post HTTP {resp.status_code}", resp.status_code)
            return {"success": True, "blocked": False, "data": resp.json(), "status_code": resp.status_code, "error": None}
        except httpx.HTTPError as e:
            return _fail(f"Ayrshare network error: {e}")

    async def delete_post(self, post_id: str) -> dict[str, Any]:
        """Delete a post."""
        if not self._is_configured():
            return _blocked("AYRSHARE_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.delete(f"{self.BASE_URL}/post/{post_id}", headers=self._headers())
            return {"success": resp.status_code in (200, 204), "blocked": False, "data": None, "status_code": resp.status_code, "error": None}
        except httpx.HTTPError as e:
            return _fail(f"Ayrshare network error: {e}")

    async def get_analytics(self, post_id: str, platforms: list[str]) -> dict[str, Any]:
        """Get analytics for a post."""
        if not self._is_configured():
            return _blocked("AYRSHARE_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/analytics/post",
                    json={"id": post_id, "platforms": platforms},
                    headers=self._headers(),
                )
            if resp.status_code != 200:
                return _fail(f"Ayrshare analytics HTTP {resp.status_code}", resp.status_code)
            return {"success": True, "blocked": False, "data": resp.json(), "status_code": resp.status_code, "error": None}
        except httpx.HTTPError as e:
            return _fail(f"Ayrshare network error: {e}")
