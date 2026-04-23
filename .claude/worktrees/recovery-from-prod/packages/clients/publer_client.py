"""Publer API client — social media distribution.

Publer supports: YouTube, TikTok, Instagram, X, LinkedIn, Reddit, Pinterest, Facebook, Google Business.
API docs: https://publer.io/docs/api
"""
from __future__ import annotations
import os
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _blocked(msg: str) -> dict[str, Any]:
    return {"success": False, "blocked": True, "error": msg, "data": None}


def _fail(msg: str, status_code: int = 0) -> dict[str, Any]:
    return {"success": False, "blocked": False, "error": msg, "data": None, "status_code": status_code}


class PublerClient:
    """Real HTTP client for Publer's REST API."""

    BASE_URL = "https://app.publer.io/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("PUBLER_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def get_profiles(self) -> dict[str, Any]:
        """List all connected social accounts."""
        if not self._is_configured():
            return _blocked("PUBLER_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(f"{self.BASE_URL}/accounts", headers=self._headers())
            if resp.status_code != 200:
                return _fail(f"Publer profiles HTTP {resp.status_code}", resp.status_code)
            return {"success": True, "blocked": False, "data": resp.json(), "status_code": resp.status_code, "error": None}
        except httpx.HTTPError as e:
            logger.error("publer.network_error", error=str(e))
            return _fail(f"Publer network error: {e}")

    async def create_post(
        self,
        account_ids: list[str],
        text: str,
        *,
        media_urls: Optional[list[str]] = None,
        link_url: Optional[str] = None,
        scheduled_at: Optional[str] = None,
        is_draft: bool = False,
    ) -> dict[str, Any]:
        """Create and schedule a post across selected accounts."""
        if not self._is_configured():
            return _blocked("PUBLER_API_KEY not configured")

        payload: dict[str, Any] = {
            "account_ids": account_ids,
            "text": text,
            "is_draft": is_draft,
        }
        if media_urls:
            payload["media_urls"] = media_urls
        if link_url:
            payload["link"] = link_url
        if scheduled_at:
            payload["scheduled_at"] = scheduled_at

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(f"{self.BASE_URL}/posts", json=payload, headers=self._headers())
            if resp.status_code not in (200, 201):
                return _fail(f"Publer create_post HTTP {resp.status_code}: {resp.text[:200]}", resp.status_code)
            return {"success": True, "blocked": False, "data": resp.json(), "status_code": resp.status_code, "error": None}
        except httpx.HTTPError as e:
            logger.error("publer.create_post_error", error=str(e))
            return _fail(f"Publer network error: {e}")

    async def get_post(self, post_id: str) -> dict[str, Any]:
        """Get status of a published/scheduled post."""
        if not self._is_configured():
            return _blocked("PUBLER_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(f"{self.BASE_URL}/posts/{post_id}", headers=self._headers())
            if resp.status_code != 200:
                return _fail(f"Publer get_post HTTP {resp.status_code}", resp.status_code)
            return {"success": True, "blocked": False, "data": resp.json(), "status_code": resp.status_code, "error": None}
        except httpx.HTTPError as e:
            logger.error("publer.get_post_error", error=str(e))
            return _fail(f"Publer network error: {e}")

    async def delete_post(self, post_id: str) -> dict[str, Any]:
        """Delete a scheduled post."""
        if not self._is_configured():
            return _blocked("PUBLER_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.delete(f"{self.BASE_URL}/posts/{post_id}", headers=self._headers())
            return {"success": resp.status_code in (200, 204), "blocked": False, "data": None, "status_code": resp.status_code, "error": None}
        except httpx.HTTPError as e:
            return _fail(f"Publer network error: {e}")
