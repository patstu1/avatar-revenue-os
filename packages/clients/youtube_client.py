"""YouTube Data API v3 client -- direct video upload and channel management.

Uses resumable uploads via google-api-python-client for reliable large-file transfers.
OAuth 2.0 refresh-token flow for long-lived server-side access.

API docs: https://developers.google.com/youtube/v3
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_UPLOAD_TIMEOUT = httpx.Timeout(600.0, connect=30.0)

# YouTube video category IDs:
# 1=Film, 2=Autos, 10=Music, 15=Pets, 17=Sports, 20=Gaming,
# 22=People & Blogs, 23=Comedy, 24=Entertainment, 25=News, 26=Howto, 27=Education, 28=Science
CATEGORY_PEOPLE_BLOGS = "22"


# ── Exceptions ──────────────────────────────────────────────────────────────

class YouTubeError(Exception):
    """Base exception for YouTube client errors."""
    def __init__(self, message: str, status_code: int = 0, response_body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class AuthError(YouTubeError):
    """401/403 — credentials invalid or expired."""
    pass


class PermanentError(YouTubeError):
    """4xx (non-auth) — bad request, not found, etc."""
    pass


class TransientError(YouTubeError):
    """429 or 5xx — retryable server/rate-limit errors."""
    pass


def _classify_error(status_code: int, message: str, body: Any = None) -> YouTubeError:
    if status_code in (401, 403):
        return AuthError(message, status_code, body)
    if status_code == 429 or status_code >= 500:
        return TransientError(message, status_code, body)
    return PermanentError(message, status_code, body)


# ── Client ──────────────────────────────────────────────────────────────────

class YouTubeClient:
    """Direct YouTube Data API v3 client with resumable upload support."""

    OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
    API_BASE = "https://www.googleapis.com/youtube/v3"
    UPLOAD_BASE = "https://www.googleapis.com/upload/youtube/v3/videos"

    def __init__(self):
        pass

    # ── Token management ────────────────────────────────────────────────

    async def refresh_access_token(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> dict[str, Any]:
        """Exchange a refresh token for a new access token.

        Returns: {"access_token": str, "expires_in": int, "token_type": str}
        """
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(self.OAUTH_TOKEN_URL, data=payload)

        if resp.status_code != 200:
            body = _safe_json(resp)
            raise _classify_error(resp.status_code, f"YouTube token refresh failed: HTTP {resp.status_code}", body)

        data = resp.json()
        return {
            "access_token": data["access_token"],
            "expires_in": data.get("expires_in", 3600),
            "token_type": data.get("token_type", "Bearer"),
        }

    # ── Connection verification ─────────────────────────────────────────

    async def verify_connection(self, access_token: str) -> bool:
        """Verify that the access token is valid by fetching the authenticated channel."""
        headers = _auth_header(access_token)
        params = {"part": "id", "mine": "true"}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{self.API_BASE}/channels", headers=headers, params=params)

        if resp.status_code == 200:
            data = resp.json()
            return len(data.get("items", [])) > 0
        return False

    # ── Video upload (resumable) ────────────────────────────────────────

    async def upload_video(
        self,
        credentials: dict[str, str],
        file_path_or_url: str,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        category_id: str = CATEGORY_PEOPLE_BLOGS,
        privacy: str = "private",
        is_short: bool = False,
    ) -> dict[str, Any]:
        """Upload a video to YouTube using resumable upload protocol.

        credentials: {"access_token": str} — must be a valid OAuth2 access token.
        file_path_or_url: local file path or HTTP(S) URL to video file.
        privacy: "private" | "public" | "unlisted"
        is_short: if True, adds #Shorts to title for YouTube Shorts detection.

        Returns: {"video_id": str, "url": str}
        """
        access_token = credentials["access_token"]

        # If is_short and #Shorts not in title, append it
        effective_title = title
        if is_short and "#Shorts" not in title:
            effective_title = f"{title} #Shorts"

        # Build video metadata
        snippet: dict[str, Any] = {
            "title": effective_title,
            "description": description,
            "categoryId": category_id,
        }
        if tags:
            snippet["tags"] = tags

        body = {
            "snippet": snippet,
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        # Resolve video bytes
        video_bytes = await self._resolve_video_bytes(file_path_or_url)
        content_length = len(video_bytes)

        # Step 1: Initiate resumable upload
        headers = {
            **_auth_header(access_token),
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(content_length),
            "X-Upload-Content-Type": "video/*",
        }
        params = {
            "uploadType": "resumable",
            "part": "snippet,status",
        }

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            init_resp = await client.post(
                self.UPLOAD_BASE,
                headers=headers,
                params=params,
                json=body,
            )

        if init_resp.status_code != 200:
            resp_body = _safe_json(init_resp)
            raise _classify_error(
                init_resp.status_code,
                f"YouTube upload init failed: HTTP {init_resp.status_code}",
                resp_body,
            )

        upload_url = init_resp.headers.get("Location")
        if not upload_url:
            raise PermanentError("YouTube upload init did not return a Location header")

        # Step 2: Upload the video bytes via resumable PUT
        upload_headers = {
            "Content-Type": "video/*",
            "Content-Length": str(content_length),
        }

        async with httpx.AsyncClient(timeout=_UPLOAD_TIMEOUT) as client:
            upload_resp = await client.put(
                upload_url,
                headers=upload_headers,
                content=video_bytes,
            )

        if upload_resp.status_code not in (200, 201):
            resp_body = _safe_json(upload_resp)
            raise _classify_error(
                upload_resp.status_code,
                f"YouTube video upload failed: HTTP {upload_resp.status_code}",
                resp_body,
            )

        data = upload_resp.json()
        video_id = data["id"]
        logger.info("youtube.upload_success", video_id=video_id, title=effective_title)

        return {
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
        }

    # ── Helpers ─────────────────────────────────────────────────────────

    async def _resolve_video_bytes(self, file_path_or_url: str) -> bytes:
        """Download from URL or read from local path."""
        if file_path_or_url.startswith(("http://", "https://")):
            async with httpx.AsyncClient(timeout=_UPLOAD_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(file_path_or_url)
            if resp.status_code != 200:
                raise PermanentError(f"Failed to download video from URL: HTTP {resp.status_code}")
            return resp.content
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _read_file, file_path_or_url)


def _read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _auth_header(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text
