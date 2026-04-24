"""Repurposing worker — real FFmpeg-based video manipulation.

Takes a long-form ContentItem and produces short-form clips:
  - Downloads source video
  - Extracts clips at specified timestamps
  - Converts to vertical (9:16) for shorts/reels/TikTok
  - Burns subtitles when captions are provided
  - Uploads finished clips to cloud storage
  - Creates Asset + ContentItem records for each clip
"""

from __future__ import annotations

import logging
import os
import tempfile

import httpx

from workers.base_task import TrackedTask
from workers.celery_app import app

logger = logging.getLogger(__name__)

DERIVATIVE_PLATFORMS = ["tiktok", "instagram", "youtube"]


# ---------------------------------------------------------------------------
# Utility: download a URL to a local temp file
# ---------------------------------------------------------------------------


def _download_to_temp(url: str, suffix: str = ".mp4") -> str:
    """Download a URL to a named temp file and return the path.

    Caller is responsible for deleting the file when done.
    """
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="repurpose_src_")
    os.close(fd)
    try:
        with httpx.Client(timeout=300, follow_redirects=True) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(path, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=1024 * 256):
                        f.write(chunk)
        logger.info("Downloaded source video to %s (%d bytes)", path, os.path.getsize(path))
        return path
    except Exception:
        # Clean up on failure
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def _generate_srt(caption: str, start_sec: float, end_sec: float) -> str:
    """Generate a minimal SRT file from a single caption string.

    Splits caption into segments of ~8 words each, spread evenly across
    the clip duration.  Returns path to the temp .srt file.
    """
    words = caption.split()
    segment_size = 8
    segments = []
    for i in range(0, len(words), segment_size):
        segments.append(" ".join(words[i : i + segment_size]))

    if not segments:
        segments = [caption]

    duration = end_sec - start_sec
    seg_duration = duration / len(segments) if segments else duration

    fd, srt_path = tempfile.mkstemp(suffix=".srt", prefix="repurpose_sub_")
    os.close(fd)

    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, text in enumerate(segments):
            seg_start = idx * seg_duration
            seg_end = min((idx + 1) * seg_duration, duration)
            f.write(f"{idx + 1}\n")
            f.write(f"{_fmt_srt_time(seg_start)} --> {_fmt_srt_time(seg_end)}\n")
            f.write(f"{text}\n\n")

    return srt_path


def _fmt_srt_time(seconds: float) -> str:
    """Format seconds to SRT timestamp HH:MM:SS,mmm."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ---------------------------------------------------------------------------
# Original brief-based repurposing (kept for backward compatibility)
# ---------------------------------------------------------------------------


@app.task(base=TrackedTask, bind=True, name="workers.repurposing_worker.tasks.repurpose_content")
def repurpose_content(self) -> dict:
    """Find approved LONG_VIDEO ContentItems and create SHORT_VIDEO briefs on other platforms."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from packages.db.enums import ContentType
    from packages.db.models.content import ContentBrief, ContentItem
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    items_found = 0
    briefs_created = 0

    with Session(engine) as session:
        try:
            candidates = (
                session.execute(
                    select(ContentItem).where(
                        ContentItem.content_type == ContentType.LONG_VIDEO,
                        ContentItem.status == "approved",
                    )
                )
                .scalars()
                .all()
            )

            for item in candidates:
                items_found += 1
                existing_platform = (item.platform or "youtube").lower()

                for target_platform in DERIVATIVE_PLATFORMS:
                    if target_platform == existing_platform:
                        continue

                    already_exists = (
                        session.execute(
                            select(ContentBrief).where(
                                ContentBrief.brand_id == item.brand_id,
                                ContentBrief.target_platform == target_platform,
                                ContentBrief.title.contains(f"[repurpose:{item.id}]"),
                            )
                        )
                        .scalars()
                        .first()
                    )

                    if already_exists:
                        continue

                    brief = ContentBrief(
                        brand_id=item.brand_id,
                        creator_account_id=item.creator_account_id,
                        offer_id=item.offer_id,
                        title=f"{item.title} [repurpose:{item.id}]",
                        content_type=ContentType.SHORT_VIDEO,
                        target_platform=target_platform,
                        hook=None,
                        angle=f"Short-form derivative of {item.title}",
                        key_points=[],
                        cta_strategy=None,
                        target_duration_seconds=60,
                        tone_guidance=None,
                        brief_metadata={
                            "source_content_item_id": str(item.id),
                            "repurpose_type": "long_to_short",
                            "source_platform": existing_platform,
                        },
                        status="draft",
                    )
                    session.add(brief)
                    briefs_created += 1

                item.status = "repurposed"

            session.commit()
        except Exception:
            logger.exception("Error during content repurposing")
            session.rollback()
            return {"status": "error", "message": "repurposing failed"}

    return {
        "status": "completed",
        "items_found": items_found,
        "briefs_created": briefs_created,
    }


# ---------------------------------------------------------------------------
# Real FFmpeg-based clip extraction pipeline
# ---------------------------------------------------------------------------


@app.task(
    base=TrackedTask,
    bind=True,
    name="workers.repurposing_worker.tasks.repurpose_to_shorts",
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=300,
)
def repurpose_to_shorts(
    self,
    content_item_id: str,
    clip_specs: list[dict],
    convert_vertical: bool = True,
    target_platform: str = "tiktok",
) -> dict:
    """Extract clips from a source video and produce short-form derivatives.

    Args:
        content_item_id: UUID of the source ContentItem (must have a video Asset).
        clip_specs: List of clip definitions, each containing:
            - start_sec (float): Start timestamp in the source video.
            - end_sec (float): End timestamp in the source video.
            - caption (str, optional): Text to burn as subtitles.
            - title (str, optional): Title for the derivative ContentItem.
        convert_vertical: Whether to convert clips to 9:16 vertical format.
        target_platform: Platform the shorts are destined for.

    Returns:
        Dict with status and list of created asset/content IDs.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from packages.db.enums import ContentType
    from packages.db.models.content import Asset, ContentItem
    from packages.db.session import get_sync_engine
    from packages.media.storage import get_storage
    from packages.media.video_processor import VideoProcessor

    engine = get_sync_engine()
    storage = get_storage()
    created_clips = []
    temp_files: list[str] = []

    try:
        with Session(engine) as session:
            # ---- Load source content item and its video asset ----
            source_item = session.execute(
                select(ContentItem).where(ContentItem.id == content_item_id)
            ).scalar_one_or_none()

            if not source_item:
                raise ValueError(f"ContentItem {content_item_id} not found")

            # Find the video asset
            source_asset = None
            if source_item.video_asset_id:
                source_asset = session.execute(
                    select(Asset).where(Asset.id == source_item.video_asset_id)
                ).scalar_one_or_none()

            if not source_asset:
                # Fallback: look for any video asset linked to this content item
                source_asset = (
                    session.execute(
                        select(Asset).where(
                            Asset.content_item_id == source_item.id,
                            Asset.asset_type.in_(["video", "long_video", "source_video"]),
                        )
                    )
                    .scalars()
                    .first()
                )

            if not source_asset:
                raise ValueError(f"No video asset found for ContentItem {content_item_id}")

            source_url = source_asset.file_path
            logger.info(
                "Repurposing source: content_item=%s asset=%s url=%s",
                content_item_id,
                source_asset.id,
                source_url,
            )

            # ---- Download source video to temp ----
            source_path = _download_to_temp(source_url)
            temp_files.append(source_path)

            # Get source duration for validation
            source_duration = VideoProcessor.get_duration(source_path)
            logger.info("Source duration: %.2f seconds", source_duration)

            # ---- Process each clip spec ----
            for idx, spec in enumerate(clip_specs):
                start_sec = float(spec["start_sec"])
                end_sec = float(spec["end_sec"])
                caption = spec.get("caption")
                clip_title = spec.get(
                    "title",
                    f"{source_item.title} — Clip {idx + 1}",
                )

                # Clamp end to source duration
                if end_sec > source_duration:
                    end_sec = source_duration
                if start_sec >= end_sec:
                    logger.warning(
                        "Skipping clip %d: start_sec=%.2f >= end_sec=%.2f",
                        idx,
                        start_sec,
                        end_sec,
                    )
                    continue

                clip_temp_files: list[str] = []
                try:
                    # Step 1: Extract clip
                    _, clip_path = tempfile.mkstemp(suffix=".mp4", prefix=f"clip_{idx}_")
                    os.close(_)
                    clip_temp_files.append(clip_path)

                    VideoProcessor.extract_clip(
                        source_path,
                        clip_path,
                        start_sec,
                        end_sec,
                    )

                    current_path = clip_path

                    # Step 2: Convert to vertical if requested
                    if convert_vertical:
                        _, vert_path = tempfile.mkstemp(suffix=".mp4", prefix=f"vert_{idx}_")
                        os.close(_)
                        clip_temp_files.append(vert_path)

                        VideoProcessor.convert_to_vertical(current_path, vert_path)
                        current_path = vert_path

                    # Step 3: Burn subtitles if caption provided
                    if caption:
                        srt_path = _generate_srt(caption, 0, end_sec - start_sec)
                        clip_temp_files.append(srt_path)

                        _, sub_path = tempfile.mkstemp(suffix=".mp4", prefix=f"sub_{idx}_")
                        os.close(_)
                        clip_temp_files.append(sub_path)

                        VideoProcessor.burn_subtitles(current_path, srt_path, sub_path)
                        current_path = sub_path

                    # Step 4: Upload finished clip to storage
                    clip_duration = VideoProcessor.get_duration(current_path)
                    file_size = os.path.getsize(current_path)

                    storage_key = storage.generate_key(
                        prefix="clips",
                        extension=".mp4",
                    )
                    clip_url = storage.upload_file(
                        current_path,
                        key=storage_key,
                        content_type="video/mp4",
                    )
                    logger.info(
                        "Uploaded clip %d: %s (%.1fs, %d bytes)",
                        idx,
                        clip_url,
                        clip_duration,
                        file_size,
                    )

                    # Step 5: Create Asset record
                    asset = Asset(
                        brand_id=source_item.brand_id,
                        asset_type="short_video",
                        file_path=clip_url,
                        file_size_bytes=file_size,
                        mime_type="video/mp4",
                        duration_seconds=clip_duration,
                        width=1080 if convert_vertical else None,
                        height=1920 if convert_vertical else None,
                        storage_provider="s3" if storage.is_cloud else "local",
                        metadata_blob={
                            "source_content_item_id": str(source_item.id),
                            "source_asset_id": str(source_asset.id),
                            "clip_index": idx,
                            "start_sec": start_sec,
                            "end_sec": end_sec,
                            "converted_vertical": convert_vertical,
                            "has_subtitles": bool(caption),
                        },
                    )
                    session.add(asset)
                    session.flush()  # Get the asset ID

                    # Step 6: Create derivative ContentItem
                    clip_item = ContentItem(
                        brand_id=source_item.brand_id,
                        brief_id=source_item.brief_id,
                        script_id=source_item.script_id,
                        creator_account_id=source_item.creator_account_id,
                        title=clip_title,
                        description=caption or f"Short clip from {source_item.title}",
                        content_type=ContentType.SHORT_VIDEO,
                        platform=target_platform,
                        video_asset_id=asset.id,
                        offer_id=source_item.offer_id,
                        offer_stack=source_item.offer_stack,
                        tags=source_item.tags,
                        hashtags=source_item.hashtags,
                        status="draft",
                    )
                    session.add(clip_item)
                    session.flush()

                    # Link asset back to content item
                    asset.content_item_id = clip_item.id

                    created_clips.append(
                        {
                            "clip_index": idx,
                            "content_item_id": str(clip_item.id),
                            "asset_id": str(asset.id),
                            "url": clip_url,
                            "duration_seconds": clip_duration,
                            "start_sec": start_sec,
                            "end_sec": end_sec,
                        }
                    )

                    logger.info(
                        "Created clip %d: content_item=%s asset=%s",
                        idx,
                        clip_item.id,
                        asset.id,
                    )

                finally:
                    # Clean up per-clip temp files
                    for tf in clip_temp_files:
                        try:
                            os.unlink(tf)
                        except OSError:
                            pass

            # Commit all records
            session.commit()

    finally:
        # Clean up source temp file
        for tf in temp_files:
            try:
                os.unlink(tf)
            except OSError:
                pass

    logger.info(
        "Repurposing complete: source=%s clips_created=%d",
        content_item_id,
        len(created_clips),
    )

    # Queue clips for publishing if any were created
    if created_clips:
        for clip_info in created_clips:
            try:
                app.send_task(
                    "workers.publishing_worker.tasks.publish_content",
                    args=[clip_info["content_item_id"]],
                    queue="publishing",
                )
            except Exception:
                logger.warning(
                    "Could not queue clip %s for publishing — will be picked up later",
                    clip_info["content_item_id"],
                )

    return {
        "status": "completed",
        "source_content_item_id": content_item_id,
        "clips_created": len(created_clips),
        "clips": created_clips,
    }
