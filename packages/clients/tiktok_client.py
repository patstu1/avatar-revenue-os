"""TikTok Content Posting API client -- direct video upload and publishing.

Uses TikTok's v2 Content Posting API with chunked upload flow:
1. Initialize upload -> get upload_url + publish_id
2. Upload video bytes to upload_url
3. Finalize publish with metadata
4. Poll publish status until terminal state

API docs: https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_UPLOAD_TIMEOUT = httpx.Timeout(600.0, connect=30.0)
_POLL_INTERVAL = 5  # seconds between status polls


# ── Exceptions ──────────────────────────────────────────────────────────────

class TikTokError(Exception):
    """Base exception for TikTok client errors."""
    def __init__(self, message: str, status_code: int = 0, response_body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class AuthError(TikTokError):
    """401/403 — credentials invalid or expired."""
    pass


class PermanentError(TikTokError):
    """4xx (non-auth) — bad request, not found, etc."""
    pass


class TransientError(TikTokError):
    """429 or 5xx — retryable server/rate-limit errors."""
    pass


def _classify_error(status_code: int, message: str, body: Any = None) -> TikTokError:
    if status_code in (401, 403):
        return AuthError(message, status_code, body)
    if status_code == 429 or status_code >= 500:
        return TransientError(message, status_code, body)
    return PermanentError(message, status_code, body)


def _check_tiktok_error(data: dict, http_status: int) -> None:
    """Raise typed error if TikTok API returned an error in the JSON body."""
    error = data.get("error", {})
    code = error.get("code", "ok")
    if code == "ok":
        return
    message = error.get("message", f"TikTok API error: {code}")
    log_id = error.get("log_id", "")
    full_msg = f"{message} (code={code}, log_id={log_id})"

    if code in ("access_token_invalid", "token_expired", "scope_not_authorized"):
        raise AuthError(full_msg, http_status, data)
    if code in ("rate_limit_exceeded",):
        raise TransientError(full_msg, http_status, data)
    if code in ("internal_error", "server_error"):
        raise TransientError(full_msg, http_status, data)
    raise PermanentError(full_msg, http_status, data)


# ── Client ──────────────────────────────────────────────────────────────────

class TikTokClient:
    """Direct TikTok Content Posting API v2 client."""

    API_BASE = "https://open.tiktokapis.com/v2"
    OAUTH_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"

    def __init__(self):
        pass

    # ── Token management ────────────────────────────────────────────────

    async def refresh_token(
        self,
        client_key: str,
        client_secret: str,
        refresh_token: str,
    ) -> dict[str, Any]:
        """Refresh an OAuth2 access token.

        Returns: {"access_token": str, "refresh_token": str, "expires_in": int, "refresh_expires_in": int}
        """
        payload = {
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(self.OAUTH_TOKEN_URL, data=payload)

        if resp.status_code != 200:
            body = _safe_json(resp)
            raise _classify_error(resp.status_code, f"TikTok token refresh failed: HTTP {resp.status_code}", body)

        data = resp.json()
        _check_tiktok_error(data, resp.status_code)

        return {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_in": data.get("expires_in", 86400),
            "refresh_expires_in": data.get("refresh_expires_in", 0),
        }

    # ── Connection verification ─────────────────────────────────────────

    async def verify_connection(self, access_token: str) -> bool:
        """Verify that the access token is valid by fetching user info."""
        headers = _auth_header(access_token)
        params = {"fields": "open_id,display_name"}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self.API_BASE}/user/info/",
                headers=headers,
                params=params,
            )

        if resp.status_code != 200:
            return False
        data = resp.json()
        error_code = data.get("error", {}).get("code", "ok")
        return error_code == "ok"

    # ── Video upload flow ───────────────────────────────────────────────

    async def init_video_upload(
        self,
        access_token: str,
        video_size: int,
    ) -> dict[str, Any]:
        """Initialize a direct video upload.

        Returns: {"upload_url": str, "publish_id": str}
        """
        headers = {
            **_auth_header(access_token),
            "Content-Type": "application/json; charset=UTF-8",
        }
        payload = {
            "post_info": {
                "title": "Video",  # placeholder, real title set at finalize
                "privacy_level": "SELF_ONLY",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,
                "total_chunk_count": 1,
            },
        }

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.API_BASE}/post/publish/video/init/",
                headers=headers,
                json=payload,
            )

        if resp.status_code != 200:
            body = _safe_json(resp)
            raise _classify_error(resp.status_code, f"TikTok upload init failed: HTTP {resp.status_code}", body)

        data = resp.json()
        _check_tiktok_error(data, resp.status_code)

        publish_id = data["data"]["publish_id"]
        upload_url = data["data"]["upload_url"]

        logger.info("tiktok.upload_init", publish_id=publish_id)
        return {"upload_url": upload_url, "publish_id": publish_id}

    async def upload_video_chunk(
        self,
        upload_url: str,
        video_bytes: bytes,
    ) -> bool:
        """Upload video bytes to the pre-signed upload URL.

        Returns True on success, raises on failure.
        """
        content_length = len(video_bytes)
        headers = {
            "Content-Type": "video/mp4",
            "Content-Length": str(content_length),
            "Content-Range": f"bytes 0-{content_length - 1}/{content_length}",
        }

        async with httpx.AsyncClient(timeout=_UPLOAD_TIMEOUT) as client:
            resp = await client.put(upload_url, headers=headers, content=video_bytes)

        if resp.status_code not in (200, 201):
            body = _safe_json(resp)
            raise _classify_error(
                resp.status_code,
                f"TikTok chunk upload failed: HTTP {resp.status_code}",
                body,
            )

        logger.info("tiktok.chunk_uploaded", size=content_length)
        return True

    async def publish_finalize(
        self,
        access_token: str,
        publish_id: str,
        title: str,
        privacy_level: str = "SELF_ONLY",
    ) -> dict[str, Any]:
        """Finalize the video publish after upload completes.

        privacy_level: SELF_ONLY | MUTUAL_FOLLOW_FRIENDS | FOLLOWER_OF_CREATOR | PUBLIC_TO_EVERYONE

        Returns: {"post_id": str}

        Note: TikTok's direct post API publishes at init time. This method checks
        the publish status after upload and returns the post ID. For the direct post
        flow, title/privacy are set during init. This wrapper exists for consistency
        and to retrieve the final post ID.
        """
        # Poll until we get a terminal status
        result = await self.check_publish_status(access_token, publish_id)

        status = result.get("status", "UNKNOWN")
        if status == "PUBLISH_COMPLETE":
            post_id = result.get("post_id", publish_id)
            logger.info("tiktok.publish_complete", post_id=post_id)
            return {"post_id": post_id}
        else:
            raise PermanentError(
                f"TikTok publish failed with status: {status} — {result.get('fail_reason', 'unknown')}",
                response_body=result,
            )

    async def check_publish_status(
        self,
        access_token: str,
        publish_id: str,
    ) -> dict[str, Any]:
        """Poll publish status until terminal state. NEVER stops based on elapsed time or attempt count.

        Terminal states: PUBLISH_COMPLETE, FAILED
        Non-terminal states: PROCESSING_UPLOAD, PROCESSING_DOWNLOAD, SENDING_TO_USER_INBOX

        Returns: {"status": str, "post_id": str | None, "fail_reason": str | None}
        """
        headers = {
            **_auth_header(access_token),
            "Content-Type": "application/json; charset=UTF-8",
        }
        payload = {"publish_id": publish_id}

        terminal_states = {"PUBLISH_COMPLETE", "FAILED"}

        while True:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    f"{self.API_BASE}/post/publish/status/fetch/",
                    headers=headers,
                    json=payload,
                )

            if resp.status_code != 200:
                body = _safe_json(resp)
                # Transient HTTP errors: log and keep polling
                if resp.status_code == 429 or resp.status_code >= 500:
                    logger.warning(
                        "tiktok.status_poll_transient_error",
                        publish_id=publish_id,
                        status_code=resp.status_code,
                    )
                    await asyncio.sleep(_POLL_INTERVAL)
                    continue
                raise _classify_error(resp.status_code, f"TikTok status check failed: HTTP {resp.status_code}", body)

            data = resp.json()
            try:
                _check_tiktok_error(data, resp.status_code)
            except TransientError:
                logger.warning("tiktok.status_poll_api_transient", publish_id=publish_id)
                await asyncio.sleep(_POLL_INTERVAL)
                continue

            status_data = data.get("data", {})
            status = status_data.get("status", "UNKNOWN")

            logger.info("tiktok.status_poll", publish_id=publish_id, status=status)

            if status in terminal_states:
                return {
                    "status": status,
                    "post_id": status_data.get("publicaly_available_post_id"),
                    "fail_reason": status_data.get("fail_reason"),
                }

            await asyncio.sleep(_POLL_INTERVAL)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _auth_header(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text
