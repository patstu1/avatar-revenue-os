"""Link Shortener Client — multi-backend URL shortening with click tracking.

Supports Dub.co, Bitly, Short.io, and raw URL fallback.
Configured via environment variables or integration_manager.

Usage:
    shortener = LinkShortener()
    result = await shortener.shorten("https://example.com/very-long-affiliate-link")
    # result = {"success": True, "short_url": "https://dub.sh/abc123", "backend": "dub", ...}

    # Get click counts
    stats = await shortener.get_click_count("https://dub.sh/abc123")
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 15.0


class LinkShortener:
    """Multi-backend link shortener with automatic backend selection.

    Priority order:
        1. Dub.co (if DUB_API_KEY set)
        2. Bitly (if BITLY_API_KEY set)
        3. Short.io (if SHORTIO_API_KEY set)
        4. Raw fallback (returns original URL)

    Each backend stores the link externally; the short URL redirects
    through the provider so click tracking is automatic.
    """

    def __init__(
        self,
        *,
        preferred_backend: str = "",
        dub_api_key: str = "",
        bitly_api_key: str = "",
        shortio_api_key: str = "",
        shortio_domain: str = "",
    ):
        self.preferred_backend = preferred_backend
        self.dub_api_key = dub_api_key or os.environ.get("DUB_API_KEY", "")
        self.bitly_api_key = bitly_api_key or os.environ.get("BITLY_API_KEY", "")
        self.shortio_api_key = shortio_api_key or os.environ.get("SHORTIO_API_KEY", "")
        self.shortio_domain = shortio_domain or os.environ.get("SHORTIO_DOMAIN", "")

    def _select_backend(self) -> str:
        """Select the best available shortener backend."""
        if self.preferred_backend:
            return self.preferred_backend
        if self.dub_api_key:
            return "dub"
        if self.bitly_api_key:
            return "bitly"
        if self.shortio_api_key:
            return "shortio"
        return "raw"

    async def shorten(
        self,
        long_url: str,
        *,
        domain: str | None = None,
        tag: str = "",
        title: str = "",
    ) -> dict[str, Any]:
        """Shorten a URL using the best available backend.

        Args:
            long_url: The full URL to shorten.
            domain: Custom domain override (backend-dependent).
            tag: Tag/group for organizing links.
            title: Human-readable title for the link.

        Returns:
            dict with success, short_url, long_url, backend, link_id.
        """
        backend = self._select_backend()

        if backend == "dub":
            return await self._shorten_dub(long_url, domain=domain, tag=tag, title=title)
        elif backend == "bitly":
            return await self._shorten_bitly(long_url, domain=domain, tag=tag, title=title)
        elif backend == "shortio":
            return await self._shorten_shortio(long_url, domain=domain, title=title)
        else:
            return self._shorten_raw(long_url)

    # ── Dub.co ───────────────────────────────────────────────────────

    async def _shorten_dub(
        self,
        long_url: str,
        *,
        domain: str | None = None,
        tag: str = "",
        title: str = "",
    ) -> dict[str, Any]:
        """Shorten via Dub.co — POST https://api.dub.co/links."""
        try:
            payload: dict[str, Any] = {"url": long_url}
            if domain:
                payload["domain"] = domain
            if tag:
                payload["tagId"] = tag
            if title:
                payload["title"] = title

            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.post(
                    "https://api.dub.co/links",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.dub_api_key}",
                        "Content-Type": "application/json",
                    },
                )
                if r.status_code in (200, 201):
                    data = r.json()
                    return {
                        "success": True,
                        "short_url": data.get("shortLink", data.get("url", long_url)),
                        "long_url": long_url,
                        "backend": "dub",
                        "link_id": data.get("id", ""),
                        "data": data,
                    }
                logger.warning("Dub.co shorten failed", status=r.status_code, body=r.text[:200])
                return self._shorten_raw(long_url, note=f"dub_api_error_{r.status_code}")
        except Exception as e:
            logger.warning("Dub.co shorten exception", error=str(e))
            return self._shorten_raw(long_url, note="dub_exception")

    async def _get_clicks_dub(self, link_id: str) -> dict[str, Any]:
        """Get click analytics for a Dub.co link."""
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(
                    "https://api.dub.co/analytics",
                    params={"linkId": link_id, "event": "clicks"},
                    headers={"Authorization": f"Bearer {self.dub_api_key}"},
                )
                if r.status_code == 200:
                    data = r.json()
                    total = (
                        data
                        if isinstance(data, int)
                        else sum(d.get("clicks", 0) for d in data)
                        if isinstance(data, list)
                        else 0
                    )
                    return {"success": True, "clicks": total, "backend": "dub", "data": data}
                return {"success": False, "error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Bitly ────────────────────────────────────────────────────────

    async def _shorten_bitly(
        self,
        long_url: str,
        *,
        domain: str | None = None,
        tag: str = "",
        title: str = "",
    ) -> dict[str, Any]:
        """Shorten via Bitly — POST https://api-ssl.bitly.com/v4/shorten."""
        try:
            payload: dict[str, Any] = {"long_url": long_url}
            if domain:
                payload["domain"] = domain
            if tag:
                payload["tags"] = [tag]
            if title:
                payload["title"] = title

            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.post(
                    "https://api-ssl.bitly.com/v4/shorten",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.bitly_api_key}",
                        "Content-Type": "application/json",
                    },
                )
                if r.status_code in (200, 201):
                    data = r.json()
                    return {
                        "success": True,
                        "short_url": data.get("link", long_url),
                        "long_url": long_url,
                        "backend": "bitly",
                        "link_id": data.get("id", ""),
                        "data": data,
                    }
                logger.warning("Bitly shorten failed", status=r.status_code, body=r.text[:200])
                return self._shorten_raw(long_url, note=f"bitly_api_error_{r.status_code}")
        except Exception as e:
            logger.warning("Bitly shorten exception", error=str(e))
            return self._shorten_raw(long_url, note="bitly_exception")

    async def _get_clicks_bitly(self, bitlink: str) -> dict[str, Any]:
        """Get click summary for a Bitly link."""
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(
                    f"https://api-ssl.bitly.com/v4/bitlinks/{bitlink}/clicks/summary",
                    headers={"Authorization": f"Bearer {self.bitly_api_key}"},
                )
                if r.status_code == 200:
                    data = r.json()
                    return {"success": True, "clicks": data.get("total_clicks", 0), "backend": "bitly", "data": data}
                return {"success": False, "error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Short.io ─────────────────────────────────────────────────────

    async def _shorten_shortio(
        self,
        long_url: str,
        *,
        domain: str | None = None,
        title: str = "",
    ) -> dict[str, Any]:
        """Shorten via Short.io — POST https://api.short.io/links."""
        shortio_domain = domain or self.shortio_domain
        if not shortio_domain:
            return self._shorten_raw(long_url, note="shortio_no_domain")

        try:
            payload: dict[str, Any] = {
                "originalURL": long_url,
                "domain": shortio_domain,
            }
            if title:
                payload["title"] = title

            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.post(
                    "https://api.short.io/links",
                    json=payload,
                    headers={
                        "Authorization": self.shortio_api_key,
                        "Content-Type": "application/json",
                    },
                )
                if r.status_code in (200, 201):
                    data = r.json()
                    return {
                        "success": True,
                        "short_url": data.get("shortURL", data.get("secureShortURL", long_url)),
                        "long_url": long_url,
                        "backend": "shortio",
                        "link_id": str(data.get("id", "")),
                        "data": data,
                    }
                logger.warning("Short.io shorten failed", status=r.status_code, body=r.text[:200])
                return self._shorten_raw(long_url, note=f"shortio_api_error_{r.status_code}")
        except Exception as e:
            logger.warning("Short.io shorten exception", error=str(e))
            return self._shorten_raw(long_url, note="shortio_exception")

    async def _get_clicks_shortio(self, link_id: str) -> dict[str, Any]:
        """Get click statistics for a Short.io link."""
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(
                    f"https://api.short.io/links/{link_id}/clicks",
                    headers={"Authorization": self.shortio_api_key},
                )
                if r.status_code == 200:
                    data = r.json()
                    clicks = data.get("totalClicks", data.get("clicks", 0))
                    return {"success": True, "clicks": clicks, "backend": "shortio", "data": data}
                return {"success": False, "error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Raw fallback ─────────────────────────────────────────────────

    @staticmethod
    def _shorten_raw(long_url: str, note: str = "") -> dict[str, Any]:
        """Fallback: return the URL as-is when no shortener is configured."""
        return {
            "success": True,
            "short_url": long_url,
            "long_url": long_url,
            "backend": "raw",
            "link_id": "",
            "note": note or "no_shortener_configured",
        }

    # ── Unified click count ──────────────────────────────────────────

    async def get_click_count(
        self,
        short_url: str = "",
        *,
        link_id: str = "",
        backend: str = "",
    ) -> dict[str, Any]:
        """Get click count for a shortened link.

        Args:
            short_url: The short URL (used to determine backend if not specified).
            link_id: The link ID from the shortener (preferred for API calls).
            backend: Force a specific backend.

        Returns:
            dict with success, clicks, backend.
        """
        be = backend or self._select_backend()

        if be == "dub" and link_id:
            return await self._get_clicks_dub(link_id)
        elif be == "bitly" and (link_id or short_url):
            bitlink = link_id or short_url.replace("https://", "").replace("http://", "")
            return await self._get_clicks_bitly(bitlink)
        elif be == "shortio" and link_id:
            return await self._get_clicks_shortio(link_id)
        else:
            return {"success": False, "clicks": 0, "backend": be, "error": "click_tracking_not_available"}
