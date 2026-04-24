"""Unified Distribution Router — native-first publishing with automatic aggregator fallback.

Strategy:
1. Try native platform API (YouTube, TikTok, Instagram, X) using direct OAuth tokens.
2. On TransientError: fall through to aggregator chain.
3. On PermanentError: fail immediately (bad content, not retryable).
4. If native unavailable or transient-failed: try each configured aggregator.
5. Return first success; if all fail, return failure for system retry on next cycle.

No artificial caps. No rate limits. No retry ceilings imposed by the router.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

PLATFORM_MAP_AYRSHARE = {
    "youtube": "youtube", "tiktok": "tiktok", "instagram": "instagram",
    "x": "twitter", "twitter": "twitter", "linkedin": "linkedin",
    "reddit": "reddit", "pinterest": "pinterest", "facebook": "facebook",
}


# ── Error classification ──────────────────────────────────────────────────

class PublishError(Exception):
    """Base publishing error."""
    pass


class TransientError(PublishError):
    """Retryable: 429, 5xx, network timeouts. Falls through to aggregator."""
    pass


class PermanentError(PublishError):
    """Non-retryable: bad content, invalid format, auth permanently revoked."""
    pass


# ── Data contracts ─────────────────────────────────────────────────────────

@dataclass
class PublishRequest:
    """Unified publish request across all methods."""
    text: str
    platform: str
    profile_ids: list[str] = field(default_factory=list)
    media_urls: list[str] | None = None
    link_url: str | None = None
    scheduled_at: str | None = None


@dataclass
class PublishResult:
    """Unified result from any publish method."""
    success: bool
    method: str  # "native", "buffer", "publer", "ayrshare", "all_failed", "none"
    post_id: str | None = None
    post_url: str | None = None
    error: str | None = None
    raw_response: dict | None = None
    methods_tried: list[str] = field(default_factory=list)


# ── Native platform adapters ──────────────────────────────────────────────

async def _try_native_youtube(credentials: dict, content_text: str, content: Any, job: Any) -> PublishResult:
    """Publish directly to YouTube via OAuth tokens."""
    from packages.clients.youtube_client import PermanentError as YTPermanent
    from packages.clients.youtube_client import TransientError as YTTransient
    from packages.clients.youtube_client import YouTubeClient

    client = YouTubeClient()
    access_token = credentials.get("access_token")
    if not access_token:
        raise TransientError("No YouTube access token available")

    # Determine video source
    video_url = None
    title = content_text[:100] if content_text else "Untitled"
    description = ""
    tags = []
    is_short = False

    if content:
        title = getattr(content, "title", title) or title
        description = getattr(content, "description", "") or ""
        if hasattr(content, "content_type") and content.content_type in ("short", "youtube_short"):
            is_short = True
        if hasattr(content, "tags") and content.tags:
            tags = content.tags if isinstance(content.tags, list) else []

        # Get video asset URL
        if hasattr(content, "video_asset_id") and content.video_asset_id:
            try:
                from sqlalchemy.orm import Session

                from packages.db.models.content import Asset
                from packages.db.session import get_sync_engine
                engine = get_sync_engine()
                with Session(engine) as sess:
                    asset = sess.get(Asset, content.video_asset_id)
                    if asset and asset.file_path:
                        video_url = asset.file_path
            except Exception:
                pass

    if not video_url:
        raise PermanentError("No video asset available for YouTube upload")

    try:
        result = await client.upload_video(
            credentials={"access_token": access_token},
            file_path_or_url=video_url,
            title=title,
            description=description,
            tags=tags,
            privacy="public",
            is_short=is_short,
        )
        return PublishResult(
            success=True,
            method="native",
            post_id=result.get("video_id"),
            post_url=result.get("url"),
            raw_response=result,
        )
    except YTTransient as e:
        raise TransientError(f"YouTube transient: {e}")
    except YTPermanent as e:
        raise PermanentError(f"YouTube permanent: {e}")


async def _try_native_tiktok(credentials: dict, content_text: str, content: Any, job: Any) -> PublishResult:
    """Publish directly to TikTok via OAuth tokens.

    Uses the TikTok Content Posting API (v2).
    """
    import httpx

    access_token = credentials.get("access_token")
    if not access_token:
        raise TransientError("No TikTok access token available")

    # Get video URL
    video_url = None
    title = content_text[:150] if content_text else ""

    if content:
        title = getattr(content, "description", "") or getattr(content, "title", "") or title
        if hasattr(content, "video_asset_id") and content.video_asset_id:
            try:
                from sqlalchemy.orm import Session

                from packages.db.models.content import Asset
                from packages.db.session import get_sync_engine
                engine = get_sync_engine()
                with Session(engine) as sess:
                    asset = sess.get(Asset, content.video_asset_id)
                    if asset and asset.file_path and asset.file_path.startswith("http"):
                        video_url = asset.file_path
            except Exception:
                pass

    if not video_url:
        raise PermanentError("No video URL available for TikTok upload")

    # TikTok Content Posting API: init upload, then send video
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    init_payload = {
        "post_info": {"title": title[:150], "privacy_level": "PUBLIC_TO_EVERYONE"},
        "source_info": {"source": "PULL_FROM_URL", "video_url": video_url},
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
            resp = await client.post(
                "https://open.tiktokapis.com/v2/post/publish/video/init/",
                json=init_payload,
                headers=headers,
            )
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransientError(f"TikTok HTTP {resp.status_code}")
        if resp.status_code not in (200, 201):
            raise PermanentError(f"TikTok publish failed: HTTP {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        publish_id = data.get("data", {}).get("publish_id", "")
        return PublishResult(
            success=True,
            method="native",
            post_id=publish_id,
            post_url=f"https://www.tiktok.com/@user/video/{publish_id}",
            raw_response=data,
        )
    except (TransientError, PermanentError):
        raise
    except httpx.HTTPError as e:
        raise TransientError(f"TikTok network error: {e}")


async def _try_native_instagram(credentials: dict, content_text: str, content: Any, job: Any) -> PublishResult:
    """Publish directly to Instagram via Graph API.

    Uses the Instagram Graph API for business/creator accounts.
    """
    import httpx

    access_token = credentials.get("access_token")
    ig_user_id = credentials.get("platform_external_id") or credentials.get("ig_user_id")
    if not access_token or not ig_user_id:
        raise TransientError("No Instagram access token or user ID available")

    caption = content_text or ""
    media_url = None
    is_video = False

    if content:
        caption = getattr(content, "description", "") or getattr(content, "title", "") or caption
        if hasattr(content, "video_asset_id") and content.video_asset_id:
            try:
                from sqlalchemy.orm import Session

                from packages.db.models.content import Asset
                from packages.db.session import get_sync_engine
                engine = get_sync_engine()
                with Session(engine) as sess:
                    asset = sess.get(Asset, content.video_asset_id)
                    if asset and asset.file_path and asset.file_path.startswith("http"):
                        media_url = asset.file_path
                        is_video = True
            except Exception:
                pass

    if not media_url:
        raise PermanentError("No media URL available for Instagram publish")

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
            # Step 1: Create media container
            container_params: dict[str, Any] = {
                "access_token": access_token,
                "caption": caption,
            }
            if is_video:
                container_params["video_url"] = media_url
                container_params["media_type"] = "REELS"
            else:
                container_params["image_url"] = media_url

            create_resp = await client.post(
                f"https://graph.facebook.com/v19.0/{ig_user_id}/media",
                params=container_params,
            )
            if create_resp.status_code == 429 or create_resp.status_code >= 500:
                raise TransientError(f"Instagram HTTP {create_resp.status_code}")
            if create_resp.status_code != 200:
                raise PermanentError(f"Instagram container failed: HTTP {create_resp.status_code}: {create_resp.text[:300]}")

            container_id = create_resp.json().get("id")
            if not container_id:
                raise PermanentError("Instagram did not return container ID")

            # Step 2: Publish the container
            pub_resp = await client.post(
                f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish",
                params={"access_token": access_token, "creation_id": container_id},
            )
            if pub_resp.status_code == 429 or pub_resp.status_code >= 500:
                raise TransientError(f"Instagram publish HTTP {pub_resp.status_code}")
            if pub_resp.status_code != 200:
                raise PermanentError(f"Instagram publish failed: HTTP {pub_resp.status_code}: {pub_resp.text[:300]}")

            post_id = pub_resp.json().get("id", "")
            return PublishResult(
                success=True,
                method="native",
                post_id=post_id,
                post_url=f"https://www.instagram.com/p/{post_id}/",
                raw_response=pub_resp.json(),
            )
    except (TransientError, PermanentError):
        raise
    except httpx.HTTPError as e:
        raise TransientError(f"Instagram network error: {e}")


async def _try_native_x(credentials: dict, content_text: str, content: Any, job: Any) -> PublishResult:
    """Publish directly to X (Twitter) via OAuth 2.0 API v2."""
    import httpx

    access_token = credentials.get("access_token")
    if not access_token:
        raise TransientError("No X access token available")

    text = content_text or ""
    if content:
        text = getattr(content, "description", "") or getattr(content, "title", "") or text

    if not text:
        raise PermanentError("No text content for X post")

    payload: dict[str, Any] = {"text": text[:280]}

    # If there's a media URL, upload it first
    if content and hasattr(content, "video_asset_id") and content.video_asset_id:
        try:
            from sqlalchemy.orm import Session

            from packages.db.models.content import Asset
            from packages.db.session import get_sync_engine
            engine = get_sync_engine()
            with Session(engine) as sess:
                asset = sess.get(Asset, content.video_asset_id)
                if asset and asset.file_path and asset.file_path.startswith("http"):
                    pass
        except Exception:
            pass

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            resp = await client.post(
                "https://api.x.com/2/tweets",
                json=payload,
                headers=headers,
            )
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransientError(f"X API HTTP {resp.status_code}")
        if resp.status_code not in (200, 201):
            raise PermanentError(f"X post failed: HTTP {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        tweet_id = data.get("data", {}).get("id", "")
        return PublishResult(
            success=True,
            method="native",
            post_id=tweet_id,
            post_url=f"https://x.com/i/status/{tweet_id}",
            raw_response=data,
        )
    except (TransientError, PermanentError):
        raise
    except httpx.HTTPError as e:
        raise TransientError(f"X network error: {e}")


# ── Native adapter registry ───────────────────────────────────────────────

NATIVE_ADAPTERS = {
    "youtube": _try_native_youtube,
    "tiktok": _try_native_tiktok,
    "instagram": _try_native_instagram,
    "x": _try_native_x,
    "twitter": _try_native_x,
}


# ── Aggregator adapters ───────────────────────────────────────────────────

class DistributorAdapter:
    """Base interface for aggregator distribution adapters."""
    name: str = "base"

    def is_configured(self) -> bool:
        raise NotImplementedError

    def supports_platform(self, platform: str) -> bool:
        return True

    async def publish(self, request: PublishRequest) -> PublishResult:
        raise NotImplementedError

    async def get_profiles(self) -> dict[str, Any]:
        raise NotImplementedError


class BufferAdapter(DistributorAdapter):
    name = "buffer"

    def is_configured(self, creds: dict | None = None) -> bool:
        if creds and creds.get("buffer"):
            return True
        return bool(os.environ.get("BUFFER_API_KEY"))

    def supports_platform(self, platform: str) -> bool:
        return platform.lower() not in ("reddit", "pinterest")

    async def publish(self, request: PublishRequest, api_key: str | None = None) -> PublishResult:
        from packages.clients.external_clients import BufferClient
        client = BufferClient(api_key=api_key)
        if not client._is_configured():
            return PublishResult(success=False, method=self.name, error="Buffer not configured — add API key in Settings > Integrations")

        # Append CTA link to post text if present
        post_text = request.text
        if request.link_url:
            post_text = f"{post_text}\n\n{request.link_url}"

        # Build media/assets for Buffer GraphQL API
        media = None
        if request.media_urls:
            url = request.media_urls[0]
            if any(url.lower().endswith(ext) for ext in (".mp4", ".mov", ".avi", ".webm")):
                media = {"video": url}
            else:
                media = {"photo": url}

        # Instagram requires explicit type metadata
        platform_lower = request.platform.lower()
        metadata = None
        if platform_lower == "instagram":
            metadata = {"instagram": {"type": "post", "shouldShareToFeed": True}}

        result = await client.create_update(
            profile_ids=request.profile_ids,
            text=post_text,
            media=media,
            metadata=metadata,
            scheduled_at=request.scheduled_at,
        )
        if result.get("success"):
            post_id = result.get("data", {}).get("updates", [{}])[0].get("id", "") if isinstance(result.get("data"), dict) else ""
            return PublishResult(success=True, method=self.name, post_id=str(post_id), raw_response=result)
        return PublishResult(success=False, method=self.name, error=result.get("error", "Buffer publish failed"), raw_response=result)

    async def get_profiles(self) -> dict[str, Any]:
        from packages.clients.external_clients import BufferClient
        return await BufferClient().get_profiles()


class PublerAdapter(DistributorAdapter):
    name = "publer"

    def is_configured(self, creds: dict | None = None) -> bool:
        if creds and creds.get("publer"):
            return True
        return bool(os.environ.get("PUBLER_API_KEY"))

    async def publish(self, request: PublishRequest, api_key: str | None = None) -> PublishResult:
        from packages.clients.publer_client import PublerClient
        client = PublerClient(api_key=api_key)
        if not client._is_configured():
            return PublishResult(success=False, method=self.name, error="Publer not configured — add API key in Settings > Integrations")

        account_ids = request.profile_ids or []
        result = await client.create_post(
            account_ids=account_ids,
            text=request.text,
            media_urls=request.media_urls,
            link_url=request.link_url,
            scheduled_at=request.scheduled_at,
        )
        if result.get("success"):
            post_id = result.get("data", {}).get("id", "") if isinstance(result.get("data"), dict) else ""
            return PublishResult(success=True, method=self.name, post_id=str(post_id), raw_response=result)
        return PublishResult(success=False, method=self.name, error=result.get("error", "Publer publish failed"), raw_response=result)

    async def get_profiles(self) -> dict[str, Any]:
        from packages.clients.publer_client import PublerClient
        return await PublerClient().get_profiles()


class AyrshareAdapter(DistributorAdapter):
    name = "ayrshare"

    def is_configured(self, creds: dict | None = None) -> bool:
        if creds and creds.get("ayrshare"):
            return True
        return bool(os.environ.get("AYRSHARE_API_KEY"))

    async def publish(self, request: PublishRequest, api_key: str | None = None) -> PublishResult:
        from packages.clients.ayrshare_client import AyrshareClient
        client = AyrshareClient(api_key=api_key)
        if not client._is_configured():
            return PublishResult(success=False, method=self.name, error="Ayrshare not configured — add API key in Settings > Integrations")

        platform_key = PLATFORM_MAP_AYRSHARE.get(request.platform.lower(), request.platform.lower())
        result = await client.create_post(
            platforms=[platform_key],
            text=request.text,
            media_urls=request.media_urls,
            link_url=request.link_url,
            scheduled_date=request.scheduled_at,
        )
        if result.get("success"):
            post_id = result.get("data", {}).get("id", "") if isinstance(result.get("data"), dict) else ""
            return PublishResult(success=True, method=self.name, post_id=str(post_id), raw_response=result)
        return PublishResult(success=False, method=self.name, error=result.get("error", "Ayrshare publish failed"), raw_response=result)

    async def get_profiles(self) -> dict[str, Any]:
        from packages.clients.ayrshare_client import AyrshareClient
        return await AyrshareClient().get_profiles()


_AGGREGATOR_REGISTRY: list[DistributorAdapter] = [
    BufferAdapter(),
    PublerAdapter(),
    AyrshareAdapter(),
]

_ADAPTER_REGISTRY = _AGGREGATOR_REGISTRY  # backward-compatible alias

_success_count: dict[str, int] = {}
_failure_count: dict[str, int] = {}


# ── Credential resolution ─────────────────────────────────────────────────

def _load_native_credentials(session, account, org_id) -> dict | None:
    """Load OAuth credentials for a native platform account.

    Checks CreatorPlatformAccount for direct_oauth connection, then
    loads tokens from IntegrationProvider (encrypted DB, .env fallback).
    Returns dict with access_token + metadata, or None if unavailable.
    """
    from sqlalchemy import select

    from apps.api.services.integration_manager import _decrypt
    from packages.db.models.integration_registry import CreatorPlatformAccount, IntegrationProvider

    platform = account.platform.value if hasattr(account.platform, "value") else str(account.platform)

    # Look for a CreatorPlatformAccount connected via direct_oauth
    cpa = session.execute(
        select(CreatorPlatformAccount).where(
            CreatorPlatformAccount.organization_id == org_id,
            CreatorPlatformAccount.brand_id == account.brand_id,
            CreatorPlatformAccount.platform == platform,
            CreatorPlatformAccount.connection_status == "connected",
            CreatorPlatformAccount.connected_via == "direct_oauth",
            CreatorPlatformAccount.is_active.is_(True),
        )
    ).scalar_one_or_none()

    if not cpa:
        return None

    # Map platform to analytics provider key for OAuth token lookup
    platform_provider_map = {
        "youtube": "youtube_analytics",
        "tiktok": "tiktok_analytics",
        "instagram": "instagram_analytics",
        "x": "x_analytics",
        "twitter": "x_analytics",
    }
    provider_key = platform_provider_map.get(platform.lower())
    if not provider_key:
        return None

    # Load the OAuth token from IntegrationProvider
    provider = session.execute(
        select(IntegrationProvider).where(
            IntegrationProvider.organization_id == org_id,
            IntegrationProvider.provider_key == provider_key,
            IntegrationProvider.is_enabled.is_(True),
        )
    ).scalar_one_or_none()

    if not provider:
        return None

    access_token = None
    if provider.oauth_token_encrypted:
        access_token = _decrypt(provider.oauth_token_encrypted)
    if not access_token and provider.api_key_encrypted:
        access_token = _decrypt(provider.api_key_encrypted)

    if not access_token:
        return None

    return {
        "access_token": access_token,
        "platform_external_id": cpa.platform_external_id,
        "ig_user_id": cpa.platform_external_id,
        "refresh_token": _decrypt(provider.oauth_refresh_encrypted) if provider.oauth_refresh_encrypted else None,
        "extra_config": provider.extra_config or {},
    }


# ── Aggregator credential loading ─────────────────────────────────────────

def _load_aggregator_credentials(session, org_id) -> dict[str, str | None]:
    """Load credentials for aggregator providers from encrypted DB.

    Uses credential_loader (DB-first, .env fallback) so aggregator adapters
    don't need to call os.environ directly.
    """
    if not session or not org_id:
        return {}
    try:
        from packages.clients.credential_loader import load_credential
        return {
            key: load_credential(session, org_id, key)
            for key in ("buffer", "publer", "ayrshare")
        }
    except Exception:
        return {}


# ── Core routing function ─────────────────────────────────────────────────

async def route_and_publish(db_session, publish_job, content_item, account, org_id) -> PublishResult:
    """Native-first, aggregator-fallback publish dispatch.

    1. Check if platform has a native adapter + valid OAuth tokens.
    2. Try native publish.
       - On success: return immediately with method="native".
       - On TransientError: fall through to aggregators.
       - On PermanentError: return failure immediately.
    3. Try each configured aggregator in reliability order.
    4. Return first success or all_failed.
    """
    platform = account.platform.value if hasattr(account.platform, "value") else str(account.platform)
    platform_lower = platform.lower()
    methods_tried: list[str] = []

    # Resolve content text
    content_text = ""
    if content_item:
        content_text = getattr(content_item, "description", "") or getattr(content_item, "title", "") or ""

    # ── Phase 1: Native API ────────────────────────────────────────────
    native_adapter = NATIVE_ADAPTERS.get(platform_lower)
    if native_adapter:
        try:
            credentials = _load_native_credentials(db_session, account, org_id)
            if credentials:
                methods_tried.append(f"native_{platform_lower}")
                logger.info("publish.trying_native platform=%s org=%s", platform_lower, org_id)
                result = await native_adapter(credentials, content_text, content_item, publish_job)
                if result.success:
                    _success_count[f"native_{platform_lower}"] = _success_count.get(f"native_{platform_lower}", 0) + 1
                    result.methods_tried = methods_tried
                    logger.info("publish.native_success platform=%s post_id=%s", platform_lower, result.post_id)
                    return result
        except PermanentError as e:
            _failure_count[f"native_{platform_lower}"] = _failure_count.get(f"native_{platform_lower}", 0) + 1
            logger.warning("publish.native_permanent_error platform=%s error=%s", platform_lower, str(e))
            return PublishResult(
                success=False,
                method=f"native_{platform_lower}",
                error=str(e),
                methods_tried=methods_tried,
            )
        except TransientError as e:
            _failure_count[f"native_{platform_lower}"] = _failure_count.get(f"native_{platform_lower}", 0) + 1
            logger.warning("publish.native_transient platform=%s error=%s — falling through to aggregators", platform_lower, str(e))
        except Exception:
            logger.exception("publish.native_unexpected platform=%s", platform_lower)

    # ── Phase 2: Aggregator fallback ───────────────────────────────────
    aggregator_creds = _load_aggregator_credentials(db_session, org_id)
    ordered = _get_aggregator_order_with_creds(platform, aggregator_creds)
    last_error = ""

    for adapter in ordered:
        methods_tried.append(adapter.name)
        try:
            request = PublishRequest(
                text=content_text,
                platform=platform,
                profile_ids=_resolve_profile_ids(db_session, publish_job, adapter.name),
                media_urls=_resolve_media_urls(content_item),
                scheduled_at=publish_job.scheduled_at.isoformat() if publish_job.scheduled_at else None,
            )
            result = await adapter.publish(request, api_key=aggregator_creds.get(adapter.name))
            if result.success:
                _success_count[adapter.name] = _success_count.get(adapter.name, 0) + 1
                result.methods_tried = methods_tried
                logger.info("publish.aggregator_success distributor=%s platform=%s", adapter.name, platform)
                return result

            _failure_count[adapter.name] = _failure_count.get(adapter.name, 0) + 1
            last_error = result.error or "unknown error"
            logger.warning("publish.aggregator_failed distributor=%s error=%s", adapter.name, last_error)
        except Exception as e:
            _failure_count[adapter.name] = _failure_count.get(adapter.name, 0) + 1
            last_error = str(e)
            logger.exception("publish.aggregator_exception distributor=%s", adapter.name)

    # ── All methods exhausted ──────────────────────────────────────────
    return PublishResult(
        success=False,
        method="all_failed",
        error=f"All publish methods failed. Last error: {last_error}" if last_error else "No publishing method available.",
        methods_tried=methods_tried,
    )


# ── Helpers ────────────────────────────────────────────────────────────────

def _resolve_profile_ids(session, job, distributor_name: str) -> list[str]:
    """Resolve aggregator-specific profile/account IDs for the publish job."""
    if distributor_name == "buffer":
        try:
            from packages.db.models.buffer_distribution import BufferProfile
            profile = session.query(BufferProfile).filter(
                BufferProfile.brand_id == job.brand_id,
                BufferProfile.platform == job.platform,
                BufferProfile.is_active.is_(True),
                BufferProfile.credential_status == "connected",
            ).first()
            if profile and profile.buffer_profile_id:
                return [profile.buffer_profile_id]
        except Exception:
            pass
    return []


def _resolve_media_urls(content_item) -> list[str] | None:
    """Extract media URLs from content item if available."""
    if not content_item:
        return None
    if hasattr(content_item, "video_asset_id") and content_item.video_asset_id:
        try:
            from sqlalchemy.orm import Session

            from packages.db.models.content import Asset
            from packages.db.session import get_sync_engine
            engine = get_sync_engine()
            with Session(engine) as sess:
                asset = sess.get(Asset, content_item.video_asset_id)
                if asset and asset.file_path and asset.file_path.startswith("http"):
                    return [asset.file_path]
        except Exception:
            pass
    return None


# ── Aggregator ordering with DB credentials ──────────────────────────────

def _get_aggregator_order_with_creds(platform: str, creds: dict) -> list[DistributorAdapter]:
    """Return aggregators ordered by reliability, considering DB credentials."""
    available = [
        a for a in _AGGREGATOR_REGISTRY
        if a.is_configured(creds=creds) and a.supports_platform(platform)
    ]
    if not available:
        return []

    def reliability(adapter: DistributorAdapter) -> float:
        s = _success_count.get(adapter.name, 0)
        f = _failure_count.get(adapter.name, 0)
        total = s + f
        if total == 0:
            return 0.5
        return s / total

    return sorted(available, key=reliability, reverse=True)


# ── Legacy-compatible functions (used by auto_publish.py and others) ──────

def get_configured_distributors() -> list[DistributorAdapter]:
    """Return all aggregators that have credentials configured."""
    return [a for a in _AGGREGATOR_REGISTRY if a.is_configured()]


def get_available_for_platform(platform: str) -> list[DistributorAdapter]:
    """Return configured aggregators that support a specific platform."""
    return [a for a in get_configured_distributors() if a.supports_platform(platform)]


def get_priority_order(platform: str) -> list[DistributorAdapter]:
    """Return aggregators ordered by reliability score (success rate)."""
    available = get_available_for_platform(platform)
    if not available:
        return []

    def reliability(adapter: DistributorAdapter) -> float:
        s = _success_count.get(adapter.name, 0)
        f = _failure_count.get(adapter.name, 0)
        total = s + f
        if total == 0:
            return 0.5
        return s / total

    return sorted(available, key=reliability, reverse=True)


async def publish_with_failover(request: PublishRequest, creds: dict | None = None) -> PublishResult:
    """Aggregator-only publish with failover. Used by auto_publish bridge.

    If *creds* dict is provided (loaded from encrypted DB), adapters use
    those credentials. Otherwise falls back to env vars.
    """
    if creds:
        ordered = _get_aggregator_order_with_creds(request.platform, creds)
    else:
        ordered = get_priority_order(request.platform)

    if not ordered:
        return PublishResult(
            success=False, method="none",
            error="No publishing service configured. Add API keys in Settings > Integrations.",
        )

    tried: list[str] = []
    last_error = ""

    for adapter in ordered:
        tried.append(adapter.name)
        try:
            result = await adapter.publish(request, api_key=creds.get(adapter.name) if creds else None)
            if result.success:
                _success_count[adapter.name] = _success_count.get(adapter.name, 0) + 1
                result.methods_tried = tried
                logger.info("publish.success distributor=%s platform=%s", adapter.name, request.platform)
                return result

            _failure_count[adapter.name] = _failure_count.get(adapter.name, 0) + 1
            last_error = result.error or "unknown error"
            logger.warning("publish.failed distributor=%s error=%s, trying next", adapter.name, last_error)
        except Exception as e:
            _failure_count[adapter.name] = _failure_count.get(adapter.name, 0) + 1
            last_error = str(e)
            logger.exception("publish.exception distributor=%s", adapter.name)

    return PublishResult(
        success=False, method="none",
        error=f"All distributors failed. Last error: {last_error}",
        methods_tried=tried,
    )


def any_distributor_configured(creds: dict | None = None) -> bool:
    """Check if at least one distribution method is available."""
    if creds:
        return any(creds.get(a.name) for a in _AGGREGATOR_REGISTRY)
    return len(get_configured_distributors()) > 0


def get_distributor_status() -> dict[str, Any]:
    """Return status of all distributors for readiness checks."""
    return {
        "configured": [a.name for a in get_configured_distributors()],
        "available_count": len(get_configured_distributors()),
        "native_platforms": list(NATIVE_ADAPTERS.keys()),
        "all_distributors": [
            {
                "name": a.name,
                "configured": a.is_configured(),
                "successes": _success_count.get(a.name, 0),
                "failures": _failure_count.get(a.name, 0),
            }
            for a in _AGGREGATOR_REGISTRY
        ],
        "native_stats": {
            platform: {
                "successes": _success_count.get(f"native_{platform}", 0),
                "failures": _failure_count.get(f"native_{platform}", 0),
            }
            for platform in NATIVE_ADAPTERS
        },
    }
