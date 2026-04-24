"""Beehiiv API v2 client — newsletter subscriber sync and campaign management.

API docs: https://developers.beehiiv.com/docs/v2
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
BASE_URL = "https://api.beehiiv.com/v2"


class BeehiivError(Exception):
    def __init__(self, message: str, status_code: int = 0, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class BeehiivClient:
    """Async Beehiiv API v2 client."""

    def __init__(self, api_key: str):
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{BASE_URL}{path}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.request(method, url, headers=self._headers(), **kwargs)
            if resp.status_code >= 400:
                raise BeehiivError(
                    f"Beehiiv API error: {resp.status_code} {resp.text}",
                    status_code=resp.status_code,
                    body=resp.text,
                )
            return resp.json() if resp.content else None

    # ── Publications ────────────────────────────────────────────────

    async def list_publications(self) -> list[dict]:
        """List all publications for the authenticated user."""
        data = await self._request("GET", "/publications")
        return data.get("data", [])

    # ── Subscribers ─────────────────────────────────────────────────

    async def list_subscribers(
        self,
        publication_id: str,
        page: int = 1,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> dict:
        """List subscribers with pagination. status: active, inactive, all."""
        params: dict[str, Any] = {"page": page, "limit": limit}
        if status:
            params["status"] = status
        return await self._request(
            "GET", f"/publications/{publication_id}/subscriptions", params=params
        )

    async def get_subscriber(self, publication_id: str, subscriber_id: str) -> dict:
        data = await self._request(
            "GET", f"/publications/{publication_id}/subscriptions/{subscriber_id}"
        )
        return data.get("data", {})

    async def create_subscriber(
        self,
        publication_id: str,
        email: str,
        reactivate_existing: bool = False,
        send_welcome_email: bool = False,
        utm_source: Optional[str] = None,
    ) -> dict:
        body: dict[str, Any] = {
            "email": email,
            "reactivate_existing": reactivate_existing,
            "send_welcome_email": send_welcome_email,
        }
        if utm_source:
            body["utm_source"] = utm_source
        data = await self._request(
            "POST", f"/publications/{publication_id}/subscriptions", json=body
        )
        return data.get("data", {})

    async def get_subscriber_count(self, publication_id: str) -> int:
        """Get total active subscriber count."""
        data = await self.list_subscribers(publication_id, page=1, limit=1, status="active")
        return data.get("total_results", 0)

    # ── Campaigns (Posts) ───────────────────────────────────────────

    async def list_posts(
        self,
        publication_id: str,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> dict:
        """List email posts/campaigns. status: draft, confirmed, archived."""
        params: dict[str, Any] = {"page": page, "limit": limit, "expand[]": "stats"}
        if status:
            params["status"] = status
        return await self._request(
            "GET", f"/publications/{publication_id}/posts", params=params
        )

    async def get_post(self, publication_id: str, post_id: str) -> dict:
        """Get a single post with stats."""
        data = await self._request(
            "GET", f"/publications/{publication_id}/posts/{post_id}", params={"expand[]": "stats"}
        )
        return data.get("data", {})
