"""Publish-readiness contract and validator.

Single source of truth for the question:
    "Is this ContentItem actually ready to publish on its intended platform?"

This is enforced at THREE gate points:

    1. Quality-gate auto-approval (content_generation_service.score_and_approve_content)
    2. Manual approval (content_pipeline_service.approve_content)
    3. Studio auto-approval (cinema_studio_worker.auto_approve_studio_content)
    4. Buffer job materialization (buffer_distribution_service.recompute_publish_jobs)

An item that fails the contract is moved to `pending_media` status (or kept at
`qa_complete`) with a stored `readiness_blocker` reason so operators can see
exactly what is missing. The item will NOT flow into Buffer publish jobs.

Contract summary:

    text_post         : non-empty text; no media required
    static_image      : publicly-accessible image asset required
    carousel          : publicly-accessible image asset required (first image)
    short_video       : publicly-accessible video asset required
    long_video        : publicly-accessible video asset required
    story             : publicly-accessible image OR video asset required
    live_stream       : not supported on the current Buffer path

Platform-specific overlays:

    instagram / x / tiktok / youtube / linkedin / facebook: inherited from
    content_type contract + the platform-specific rules enforced by
    `packages.scoring.buffer_engine.validate_publish_payload`.

This module intentionally does NOT duplicate the Buffer payload validator —
that validator runs just before the Buffer API call. This one runs BEFORE a
ContentItem is allowed to transition into `approved` state at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.content import Asset, ContentItem

# Platforms that require a media asset to publish at all.
MEDIA_REQUIRED_PLATFORMS = {"instagram", "tiktok", "youtube"}

# Content types that require a specific asset shape.
REQUIRES_VIDEO_ASSET = {"short_video", "long_video", "live_stream"}
REQUIRES_IMAGE_ASSET = {"static_image", "carousel"}
REQUIRES_ANY_MEDIA = REQUIRES_VIDEO_ASSET | REQUIRES_IMAGE_ASSET | {"story"}
TEXT_ONLY_ALLOWED = {"text_post"}


@dataclass
class ReadinessResult:
    """Honest readiness verdict for a ContentItem."""
    ok: bool
    reason: str   # machine-queryable code (empty if ok)
    detail: str   # short human-readable sentence

    def __bool__(self) -> bool:  # allow `if result:` usage
        return self.ok


def _is_public_http_url(path: str | None) -> bool:
    if not path:
        return False
    return path.startswith("http://") or path.startswith("https://")


def _is_video_mime(mime: str | None) -> bool:
    if not mime:
        return False
    return mime.startswith("video/")


def _is_image_mime(mime: str | None) -> bool:
    if not mime:
        return False
    return mime.startswith("image/")


async def _load_asset(db: AsyncSession, asset_id: UUID | None) -> Asset | None:
    if not asset_id:
        return None
    return (
        await db.execute(select(Asset).where(Asset.id == asset_id))
    ).scalar_one_or_none()


async def check_publish_readiness(
    db: AsyncSession, item: ContentItem
) -> ReadinessResult:
    """Single-source-of-truth readiness check for a ContentItem.

    Returns a `ReadinessResult` with:
        ok=True/False
        reason=<machine code>
        detail=<human sentence>

    Machine codes (stable, queryable):
        ok
        empty_text_and_no_media
        missing_video_asset
        missing_image_asset
        missing_any_media
        media_asset_not_public
        invalid_asset_mime_type
        unsupported_content_type
        unsupported_platform_contract
    """
    # Normalize content_type
    ct_raw = item.content_type
    ct = (getattr(ct_raw, "value", None) or str(ct_raw or "")).lower()

    # Normalize platform (may be None)
    platform_raw = item.platform
    platform = (getattr(platform_raw, "value", None) or str(platform_raw or "")).lower()

    title = (item.title or "").strip()
    description = (getattr(item, "description", None) or "").strip()
    has_text = bool(title or description)

    # Text-only: no media required, but must have text
    if ct in TEXT_ONLY_ALLOWED:
        if not has_text:
            return ReadinessResult(
                ok=False,
                reason="empty_text_and_no_media",
                detail="text_post has no title or description",
            )
        # Text posts are not supported on instagram/tiktok/youtube media-first platforms
        if platform in MEDIA_REQUIRED_PLATFORMS:
            return ReadinessResult(
                ok=False,
                reason="unsupported_platform_contract",
                detail=f"text_post content_type cannot be published on {platform}",
            )
        return ReadinessResult(ok=True, reason="ok", detail="text-only post ready")

    # Everything else needs a media asset.
    if ct not in REQUIRES_ANY_MEDIA:
        return ReadinessResult(
            ok=False,
            reason="unsupported_content_type",
            detail=f"content_type '{ct}' is not supported by the current publish path",
        )

    # Load referenced assets once
    video_asset = await _load_asset(db, item.video_asset_id)
    thumbnail_asset = await _load_asset(db, item.thumbnail_asset_id)

    # Pick the asset that matches the content_type expectation
    if ct in REQUIRES_VIDEO_ASSET:
        if not video_asset:
            return ReadinessResult(
                ok=False,
                reason="missing_video_asset",
                detail=f"{ct} requires video_asset_id to be linked",
            )
        if not _is_public_http_url(video_asset.file_path):
            return ReadinessResult(
                ok=False,
                reason="media_asset_not_public",
                detail=f"video asset {video_asset.id} file_path is not a public http(s) URL",
            )
        # Instagram+Reels specifically require video (enforced by buffer_engine too)
        if platform == "instagram" and not (_is_video_mime(video_asset.mime_type) or (video_asset.file_path or "").lower().endswith((".mp4", ".mov", ".webm", ".m4v"))):
            return ReadinessResult(
                ok=False,
                reason="invalid_asset_mime_type",
                detail=f"instagram {ct} requires a video file, asset mime is '{video_asset.mime_type}'",
            )
        return ReadinessResult(ok=True, reason="ok", detail="video asset linked and public")

    if ct in REQUIRES_IMAGE_ASSET:
        # Prefer thumbnail_asset (what image posts should use), fall back to video_asset
        asset = thumbnail_asset or video_asset
        if not asset:
            return ReadinessResult(
                ok=False,
                reason="missing_image_asset",
                detail=f"{ct} requires thumbnail_asset_id or video_asset_id to be linked to an image",
            )
        if not _is_public_http_url(asset.file_path):
            return ReadinessResult(
                ok=False,
                reason="media_asset_not_public",
                detail=f"image asset {asset.id} file_path is not a public http(s) URL",
            )
        return ReadinessResult(ok=True, reason="ok", detail="image asset linked and public")

    # story: either image or video works
    if ct == "story":
        asset = video_asset or thumbnail_asset
        if not asset:
            return ReadinessResult(
                ok=False,
                reason="missing_any_media",
                detail="story requires at least one linked image or video asset",
            )
        if not _is_public_http_url(asset.file_path):
            return ReadinessResult(
                ok=False,
                reason="media_asset_not_public",
                detail=f"story asset {asset.id} file_path is not a public http(s) URL",
            )
        return ReadinessResult(ok=True, reason="ok", detail="story asset linked and public")

    return ReadinessResult(
        ok=False,
        reason="unsupported_content_type",
        detail=f"content_type '{ct}' is not handled by the readiness contract",
    )
