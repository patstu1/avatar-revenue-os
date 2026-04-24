"""Instagram Graph API client -- direct media publishing (Reels, Images, Carousels).

Uses the Instagram Content Publishing API (Graph API v21.0):
1. Create a media container (upload phase)
2. Poll container status until FINISHED
3. Publish the container to the feed

API docs: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_POLL_INTERVAL = 5  # seconds between status polls


# ── Exceptions ──────────────────────────────────────────────────────────────

class InstagramError(Exception):
    """Base exception for Instagram client errors."""
    def __init__(self, message: str, status_code: int = 0, response_body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class AuthError(InstagramError):
    """401/403 — credentials invalid or expired."""
    pass


class PermanentError(InstagramError):
    """4xx (non-auth) — bad request, not found, etc."""
    pass


class TransientError(InstagramError):
    """429 or 5xx — retryable server/rate-limit errors."""
    pass


def _classify_error(status_code: int, message: str, body: Any = None) -> InstagramError:
    if status_code in (401, 403):
        return AuthError(message, status_code, body)
    if status_code == 429 or status_code >= 500:
        return TransientError(message, status_code, body)
    return PermanentError(message, status_code, body)


def _check_graph_error(data: dict, http_status: int) -> None:
    """Raise typed error if the Graph API returned an error object."""
    error = data.get("error")
    if not error:
        return
    code = error.get("code", 0)
    message = error.get("message", "Unknown Instagram Graph API error")
    error_type = error.get("type", "")
    full_msg = f"{message} (type={error_type}, code={code})"

    if code in (190, 102):  # expired/invalid token
        raise AuthError(full_msg, http_status, data)
    if code in (4, 17, 32, 613):  # rate limit / too many calls
        raise TransientError(full_msg, http_status, data)
    if code in (1, 2):  # temporary server issues
        raise TransientError(full_msg, http_status, data)
    raise PermanentError(full_msg, http_status, data)


# ── Client ──────────────────────────────────────────────────────────────────

class InstagramClient:
    """Direct Instagram Graph API client for content publishing."""

    GRAPH_BASE = "https://graph.instagram.com/v21.0"
    # Alternative for Business accounts using Facebook Graph API:
    FB_GRAPH_BASE = "https://graph.facebook.com/v21.0"

    def __init__(self, use_facebook_graph: bool = False):
        """Initialize client.

        use_facebook_graph: if True, use graph.facebook.com instead of graph.instagram.com.
            Required for Instagram Business accounts linked to Facebook Pages.
        """
        self.base_url = self.FB_GRAPH_BASE if use_facebook_graph else self.GRAPH_BASE

    # ── Connection verification ─────────────────────────────────────────

    async def verify_connection(self, access_token: str) -> bool:
        """Verify that the access token is valid by fetching the user profile."""
        params = {"fields": "id,username", "access_token": access_token}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{self.base_url}/me", params=params)

        if resp.status_code != 200:
            return False
        data = resp.json()
        return "id" in data and "error" not in data

    # ── Reel publishing ─────────────────────────────────────────────────

    async def create_reel_container(
        self,
        access_token: str,
        ig_user_id: str,
        video_url: str,
        caption: str = "",
        share_to_feed: bool = True,
        cover_url: Optional[str] = None,
        thumb_offset: Optional[int] = None,
    ) -> str:
        """Create a Reel media container. The video must be accessible via public URL.

        Returns: creation_id (container ID to poll and then publish).
        """
        params: dict[str, Any] = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": str(share_to_feed).lower(),
            "access_token": access_token,
        }
        if cover_url:
            params["cover_url"] = cover_url
        if thumb_offset is not None:
            params["thumb_offset"] = thumb_offset

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/{ig_user_id}/media",
                params=params,
            )

        if resp.status_code != 200:
            body = _safe_json(resp)
            raise _classify_error(resp.status_code, f"Instagram reel container failed: HTTP {resp.status_code}", body)

        data = resp.json()
        _check_graph_error(data, resp.status_code)

        creation_id = data.get("id")
        if not creation_id:
            raise PermanentError("Instagram did not return a container ID", response_body=data)

        logger.info("instagram.reel_container_created", creation_id=creation_id)
        return creation_id

    # ── Image publishing ────────────────────────────────────────────────

    async def create_image_container(
        self,
        access_token: str,
        ig_user_id: str,
        image_url: str,
        caption: str = "",
        is_carousel_item: bool = False,
    ) -> str:
        """Create an image media container.

        Returns: creation_id.
        """
        params: dict[str, Any] = {
            "image_url": image_url,
            "access_token": access_token,
        }
        if is_carousel_item:
            params["is_carousel_item"] = "true"
        else:
            params["caption"] = caption

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/{ig_user_id}/media",
                params=params,
            )

        if resp.status_code != 200:
            body = _safe_json(resp)
            raise _classify_error(resp.status_code, f"Instagram image container failed: HTTP {resp.status_code}", body)

        data = resp.json()
        _check_graph_error(data, resp.status_code)

        creation_id = data.get("id")
        if not creation_id:
            raise PermanentError("Instagram did not return a container ID", response_body=data)

        logger.info("instagram.image_container_created", creation_id=creation_id)
        return creation_id

    # ── Carousel publishing ─────────────────────────────────────────────

    async def create_carousel_container(
        self,
        access_token: str,
        ig_user_id: str,
        children_ids: list[str],
        caption: str = "",
    ) -> str:
        """Create a carousel container from previously created child containers.

        children_ids: list of creation_ids from create_image_container or create_reel_container
            (each created with is_carousel_item=True).

        Returns: creation_id for the carousel.
        """
        params: dict[str, Any] = {
            "media_type": "CAROUSEL",
            "caption": caption,
            "children": ",".join(children_ids),
            "access_token": access_token,
        }

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/{ig_user_id}/media",
                params=params,
            )

        if resp.status_code != 200:
            body = _safe_json(resp)
            raise _classify_error(resp.status_code, f"Instagram carousel container failed: HTTP {resp.status_code}", body)

        data = resp.json()
        _check_graph_error(data, resp.status_code)

        creation_id = data.get("id")
        if not creation_id:
            raise PermanentError("Instagram did not return a carousel container ID", response_body=data)

        logger.info("instagram.carousel_container_created", creation_id=creation_id, children=len(children_ids))
        return creation_id

    async def create_carousel(
        self,
        access_token: str,
        ig_user_id: str,
        media_items: list[dict[str, str]],
        caption: str = "",
    ) -> str:
        """High-level: create child containers, assemble carousel, wait, publish.

        media_items: list of {"type": "image"|"video", "url": str}

        Returns: published media_id.
        """
        children_ids = []
        for item in media_items:
            if item["type"] == "image":
                cid = await self.create_image_container(
                    access_token, ig_user_id, item["url"], is_carousel_item=True,
                )
            else:
                cid = await self.create_reel_container(
                    access_token, ig_user_id, item["url"], is_carousel_item=True,
                )
            children_ids.append(cid)

        # Wait for all children to finish processing
        for cid in children_ids:
            status = await self.check_container_status(access_token, cid)
            if status != "FINISHED":
                raise PermanentError(f"Carousel child {cid} failed with status: {status}")

        # Create the carousel container
        carousel_id = await self.create_carousel_container(
            access_token, ig_user_id, children_ids, caption,
        )

        # Wait for carousel to finish processing
        status = await self.check_container_status(access_token, carousel_id)
        if status != "FINISHED":
            raise PermanentError(f"Carousel container {carousel_id} failed with status: {status}")

        # Publish
        media_id = await self.publish_container(access_token, ig_user_id, carousel_id)
        return media_id

    # ── Container status polling ────────────────────────────────────────

    async def check_container_status(
        self,
        access_token: str,
        creation_id: str,
    ) -> str:
        """Poll container status until FINISHED or ERROR. NEVER stops based on elapsed time or attempt count.

        Terminal states: FINISHED, ERROR
        Non-terminal states: IN_PROGRESS, EXPIRED (treated as error)

        Returns: terminal status string ("FINISHED" or "ERROR").
        """
        terminal_states = {"FINISHED", "ERROR", "EXPIRED"}

        while True:
            params = {
                "fields": "status_code,status",
                "access_token": access_token,
            }
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{self.base_url}/{creation_id}",
                    params=params,
                )

            if resp.status_code != 200:
                body = _safe_json(resp)
                # Transient HTTP errors: log and keep polling
                if resp.status_code == 429 or resp.status_code >= 500:
                    logger.warning(
                        "instagram.container_poll_transient_error",
                        creation_id=creation_id,
                        status_code=resp.status_code,
                    )
                    await asyncio.sleep(_POLL_INTERVAL)
                    continue
                raise _classify_error(
                    resp.status_code,
                    f"Instagram container status check failed: HTTP {resp.status_code}",
                    body,
                )

            data = resp.json()
            try:
                _check_graph_error(data, resp.status_code)
            except TransientError:
                logger.warning("instagram.container_poll_api_transient", creation_id=creation_id)
                await asyncio.sleep(_POLL_INTERVAL)
                continue

            status_code = data.get("status_code", "UNKNOWN")
            logger.info("instagram.container_poll", creation_id=creation_id, status=status_code)

            if status_code in terminal_states:
                return status_code

            await asyncio.sleep(_POLL_INTERVAL)

    # ── Publish ─────────────────────────────────────────────────────────

    async def publish_container(
        self,
        access_token: str,
        ig_user_id: str,
        creation_id: str,
    ) -> str:
        """Publish a finished media container to the Instagram feed.

        Returns: media_id of the published post.
        """
        params = {
            "creation_id": creation_id,
            "access_token": access_token,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/{ig_user_id}/media_publish",
                params=params,
            )

        if resp.status_code != 200:
            body = _safe_json(resp)
            raise _classify_error(resp.status_code, f"Instagram publish failed: HTTP {resp.status_code}", body)

        data = resp.json()
        _check_graph_error(data, resp.status_code)

        media_id = data.get("id")
        if not media_id:
            raise PermanentError("Instagram did not return a media_id", response_body=data)

        logger.info("instagram.published", media_id=media_id, creation_id=creation_id)
        return media_id


# ── Helpers ─────────────────────────────────────────────────────────────────

def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text
