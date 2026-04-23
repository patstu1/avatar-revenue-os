"""X (Twitter) API v2 client -- direct posting, media upload, and threading.

Posts text, images, and video via the X API v2 (posts) and v1.1 (media upload).
Automatically splits long text into threads at sentence boundaries.

API docs:
- Posts: https://developer.x.com/en/docs/x-api/tweets/manage-tweets/api-reference
- Media: https://developer.x.com/en/docs/x-api/media/upload-media/api-reference
- OAuth 2.0: https://developer.x.com/en/docs/authentication/oauth-2-0
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import math
import os
import re
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_UPLOAD_TIMEOUT = httpx.Timeout(300.0, connect=30.0)
_POLL_INTERVAL = 5  # seconds between media processing polls

MAX_TWEET_LENGTH = 280
# Chunked upload: 5MB chunks
CHUNK_SIZE = 5 * 1024 * 1024


# ── Exceptions ──────────────────────────────────────────────────────────────

class XError(Exception):
    """Base exception for X client errors."""
    def __init__(self, message: str, status_code: int = 0, response_body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class AuthError(XError):
    """401/403 — credentials invalid or expired."""
    pass


class PermanentError(XError):
    """4xx (non-auth) — bad request, not found, etc."""
    pass


class TransientError(XError):
    """429 or 5xx — retryable server/rate-limit errors."""
    pass


def _classify_error(status_code: int, message: str, body: Any = None) -> XError:
    if status_code in (401, 403):
        return AuthError(message, status_code, body)
    if status_code == 429 or status_code >= 500:
        return TransientError(message, status_code, body)
    return PermanentError(message, status_code, body)


# ── Client ──────────────────────────────────────────────────────────────────

class XClient:
    """Direct X (Twitter) API v2 client for posting and media upload."""

    API_V2_BASE = "https://api.x.com/2"
    MEDIA_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"
    OAUTH_TOKEN_URL = "https://api.x.com/2/oauth2/token"

    def __init__(self):
        pass

    # ── Token management ────────────────────────────────────────────────

    async def refresh_token(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> dict[str, Any]:
        """Refresh an OAuth 2.0 access token using PKCE refresh flow.

        Returns: {"access_token": str, "refresh_token": str, "expires_in": int}
        """
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }
        auth = (client_id, client_secret)
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(self.OAUTH_TOKEN_URL, data=payload, auth=auth)

        if resp.status_code != 200:
            body = _safe_json(resp)
            raise _classify_error(resp.status_code, f"X token refresh failed: HTTP {resp.status_code}", body)

        data = resp.json()
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", refresh_token),
            "expires_in": data.get("expires_in", 7200),
        }

    # ── Connection verification ─────────────────────────────────────────

    async def verify_connection(self, access_token: str) -> bool:
        """Verify that the access token is valid by fetching the authenticated user."""
        headers = _auth_header(access_token)
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{self.API_V2_BASE}/users/me", headers=headers)
        return resp.status_code == 200

    # ── Post creation ───────────────────────────────────────────────────

    async def create_post(
        self,
        access_token: str,
        text: str,
        reply_to_id: Optional[str] = None,
        quote_tweet_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a single tweet/post.

        If text > 280 chars, automatically creates a thread instead.

        Returns: {"tweet_id": str, "url": str}
        """
        # Auto-thread if text exceeds limit
        if len(text) > MAX_TWEET_LENGTH:
            parts = _smart_split(text)
            if len(parts) > 1:
                tweet_ids = await self.create_thread(access_token, parts)
                return {
                    "tweet_id": tweet_ids[0],
                    "url": f"https://x.com/i/status/{tweet_ids[0]}",
                    "thread_ids": tweet_ids,
                }

        headers = {
            **_auth_header(access_token),
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {"text": text}

        if reply_to_id:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}
        if quote_tweet_id:
            payload["quote_tweet_id"] = quote_tweet_id

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.API_V2_BASE}/tweets",
                headers=headers,
                json=payload,
            )

        if resp.status_code not in (200, 201):
            body = _safe_json(resp)
            raise _classify_error(resp.status_code, f"X create post failed: HTTP {resp.status_code}", body)

        data = resp.json()
        tweet_id = data["data"]["id"]
        logger.info("x.post_created", tweet_id=tweet_id)

        return {
            "tweet_id": tweet_id,
            "url": f"https://x.com/i/status/{tweet_id}",
        }

    async def create_post_with_media(
        self,
        access_token: str,
        text: str,
        media_ids: list[str],
    ) -> dict[str, Any]:
        """Create a post with attached media.

        media_ids: list of media IDs from upload_media().

        Returns: {"tweet_id": str, "url": str}
        """
        headers = {
            **_auth_header(access_token),
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "text": text,
            "media": {"media_ids": media_ids},
        }

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.API_V2_BASE}/tweets",
                headers=headers,
                json=payload,
            )

        if resp.status_code not in (200, 201):
            body = _safe_json(resp)
            raise _classify_error(resp.status_code, f"X create post with media failed: HTTP {resp.status_code}", body)

        data = resp.json()
        tweet_id = data["data"]["id"]
        logger.info("x.post_with_media_created", tweet_id=tweet_id, media_count=len(media_ids))

        return {
            "tweet_id": tweet_id,
            "url": f"https://x.com/i/status/{tweet_id}",
        }

    # ── Thread creation ─────────────────────────────────────────────────

    async def create_thread(
        self,
        access_token: str,
        tweets_list: list[str],
    ) -> list[str]:
        """Create a thread by posting sequential replies.

        tweets_list: list of text strings, each <= 280 chars.

        Returns: list of tweet_ids in order.
        """
        tweet_ids: list[str] = []
        reply_to_id: Optional[str] = None

        for i, text in enumerate(tweets_list):
            result = await self.create_post(
                access_token=access_token,
                text=text,
                reply_to_id=reply_to_id,
            )
            tweet_id = result["tweet_id"]
            tweet_ids.append(tweet_id)
            reply_to_id = tweet_id
            logger.info("x.thread_part", part=i + 1, total=len(tweets_list), tweet_id=tweet_id)

        return tweet_ids

    # ── Media upload (chunked) ──────────────────────────────────────────

    async def upload_media(
        self,
        credentials: dict[str, str],
        file_path: str,
        media_type: str = "image/jpeg",
    ) -> str:
        """Upload media using the chunked upload endpoint.

        credentials: {"access_token": str}
        media_type: MIME type (e.g. "image/jpeg", "image/png", "video/mp4", "image/gif")

        Returns: media_id string.
        """
        access_token = credentials["access_token"]
        headers = _auth_header(access_token)

        # Read file
        video_bytes = await _read_file_async(file_path)
        total_bytes = len(video_bytes)

        media_category = _media_category(media_type)

        # Step 1: INIT
        init_params = {
            "command": "INIT",
            "total_bytes": str(total_bytes),
            "media_type": media_type,
            "media_category": media_category,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(self.MEDIA_UPLOAD_URL, headers=headers, data=init_params)

        if resp.status_code not in (200, 201, 202):
            body = _safe_json(resp)
            raise _classify_error(resp.status_code, f"X media INIT failed: HTTP {resp.status_code}", body)

        media_id = resp.json()["media_id_string"]
        logger.info("x.media_init", media_id=media_id, total_bytes=total_bytes)

        # Step 2: APPEND (chunked)
        segment_index = 0
        offset = 0
        while offset < total_bytes:
            chunk = video_bytes[offset:offset + CHUNK_SIZE]
            async with httpx.AsyncClient(timeout=_UPLOAD_TIMEOUT) as client:
                resp = await client.post(
                    self.MEDIA_UPLOAD_URL,
                    headers=headers,
                    data={
                        "command": "APPEND",
                        "media_id": media_id,
                        "segment_index": str(segment_index),
                    },
                    files={"media_data": ("chunk", chunk, media_type)},
                )

            if resp.status_code not in (200, 201, 202, 204):
                body = _safe_json(resp)
                raise _classify_error(resp.status_code, f"X media APPEND failed: HTTP {resp.status_code}", body)

            offset += CHUNK_SIZE
            segment_index += 1
            logger.info("x.media_append", media_id=media_id, segment=segment_index)

        # Step 3: FINALIZE
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                self.MEDIA_UPLOAD_URL,
                headers=headers,
                data={"command": "FINALIZE", "media_id": media_id},
            )

        if resp.status_code not in (200, 201):
            body = _safe_json(resp)
            raise _classify_error(resp.status_code, f"X media FINALIZE failed: HTTP {resp.status_code}", body)

        finalize_data = resp.json()
        processing_info = finalize_data.get("processing_info")

        # Step 4: Poll STATUS if processing is needed (video/gif)
        if processing_info:
            await self._poll_media_status(headers, media_id)

        logger.info("x.media_upload_complete", media_id=media_id)
        return media_id

    async def _poll_media_status(
        self,
        headers: dict[str, str],
        media_id: str,
    ) -> None:
        """Poll media processing status until terminal. NEVER stops based on elapsed time or attempt count."""
        terminal_states = {"succeeded", "failed"}

        while True:
            params = {"command": "STATUS", "media_id": media_id}
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(self.MEDIA_UPLOAD_URL, headers=headers, params=params)

            if resp.status_code != 200:
                body = _safe_json(resp)
                if resp.status_code == 429 or resp.status_code >= 500:
                    logger.warning("x.media_status_transient", media_id=media_id, status_code=resp.status_code)
                    await asyncio.sleep(_POLL_INTERVAL)
                    continue
                raise _classify_error(resp.status_code, f"X media STATUS failed: HTTP {resp.status_code}", body)

            data = resp.json()
            processing = data.get("processing_info", {})
            state = processing.get("state", "unknown")

            logger.info("x.media_status_poll", media_id=media_id, state=state)

            if state in terminal_states:
                if state == "failed":
                    error = processing.get("error", {})
                    raise PermanentError(
                        f"X media processing failed: {error.get('message', 'unknown')}",
                        response_body=data,
                    )
                return

            # Use the check_after_secs hint if provided, else default interval
            wait_secs = processing.get("check_after_secs", _POLL_INTERVAL)
            await asyncio.sleep(wait_secs)


# ── Text splitting ──────────────────────────────────────────────────────────

def _smart_split(text: str, max_length: int = MAX_TWEET_LENGTH) -> list[str]:
    """Split long text into tweet-sized chunks at sentence boundaries.

    Strategy:
    1. Try splitting at sentence boundaries (. ! ?)
    2. Fall back to splitting at word boundaries
    3. Last resort: hard split at max_length
    """
    if len(text) <= max_length:
        return [text]

    parts: list[str] = []
    remaining = text.strip()

    while remaining:
        if len(remaining) <= max_length:
            parts.append(remaining)
            break

        # Find the best split point within max_length
        chunk = remaining[:max_length]

        # Try sentence boundaries first
        split_pos = _find_sentence_boundary(chunk)

        # Fall back to word boundary
        if split_pos < max_length // 3:
            split_pos = _find_word_boundary(chunk)

        # Hard split as last resort
        if split_pos < max_length // 3:
            split_pos = max_length

        parts.append(remaining[:split_pos].rstrip())
        remaining = remaining[split_pos:].lstrip()

    return parts


def _find_sentence_boundary(text: str) -> int:
    """Find the last sentence-ending punctuation position in text."""
    best = 0
    for match in re.finditer(r'[.!?]\s', text):
        best = match.end()
    # Also check if text ends with sentence punctuation
    if text and text[-1] in '.!?':
        best = max(best, len(text))
    return best


def _find_word_boundary(text: str) -> int:
    """Find the last whitespace position in text."""
    pos = text.rfind(' ')
    return pos if pos > 0 else len(text)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _auth_header(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text


def _media_category(mime_type: str) -> str:
    """Map MIME type to X media category."""
    if mime_type.startswith("video/"):
        return "tweet_video"
    if mime_type == "image/gif":
        return "tweet_gif"
    return "tweet_image"


async def _read_file_async(path: str) -> bytes:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _read_file_sync, path)


def _read_file_sync(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()
