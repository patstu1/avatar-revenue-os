"""Pipeline continuation worker — advances content through the async media pipeline.

Pipeline stages: Script -> Voice -> Avatar -> B-Roll -> Assembly -> Ready to Publish.

When an external media provider completes an async job (voice synthesis, avatar generation,
video/image rendering), the webhook handler calls continue_pipeline to persist the output
and dispatch the next stage. When all media assets are ready, assemble_and_finalize
gathers them into a content item and marks it ready for publishing.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.db.session import get_sync_engine
from packages.media.storage import get_storage
from workers.base_task import TrackedTask
from workers.celery_app import app

logger = structlog.get_logger()


def _get_session():
    """Create a new sync SQLAlchemy session."""
    return Session(get_sync_engine())


def _mime_for_job_type(job_type: str) -> str:
    """Return a sensible MIME type based on the media job type."""
    mapping = {
        "voice": "audio/mpeg",
        "avatar": "video/mp4",
        "video": "video/mp4",
        "image": "image/png",
        "music": "audio/mpeg",
        "b_roll": "video/mp4",
    }
    return mapping.get(job_type, "application/octet-stream")


def _storage_prefix_for_job_type(job_type: str) -> str:
    """Return the S3/local storage prefix for a given job type."""
    mapping = {
        "voice": "pipeline/voice",
        "avatar": "pipeline/avatar",
        "video": "pipeline/video",
        "image": "pipeline/image",
        "music": "pipeline/music",
        "b_roll": "pipeline/b_roll",
    }
    return mapping.get(job_type, "pipeline/media")


# ---------------------------------------------------------------------------
# continue_pipeline — the core continuation task
# ---------------------------------------------------------------------------


@app.task(
    base=TrackedTask,
    bind=True,
    name="workers.pipeline_worker.tasks.continue_pipeline",
)
def continue_pipeline(
    self,
    media_job_id: str,
    content_item_id: str,
    job_type: str,
    output_url: str | None = None,
) -> dict:
    """Continue the content pipeline after an async media job completes.

    Steps:
        1. Load the completed MediaJob and ContentItem from the DB.
        2. Persist the output to cloud/local storage via MediaStorage.
        3. Create or update the Asset record with the persistent URL.
        4. Determine the next pipeline stage and dispatch it.
        5. Emit a pipeline.step_completed event.

    Args:
        media_job_id:    UUID of the completed MediaJob.
        content_item_id: UUID of the ContentItem being built.
        job_type:        The type that just completed (voice | avatar | video | image | b_roll | music).
        output_url:      Provider-hosted URL to the generated media (optional if already stored).

    Returns:
        Dict with step result, persistent URL, and next action taken.
    """
    from apps.api.services.event_bus import emit_event_sync
    from packages.db.models.content import Asset, ContentItem
    from packages.db.models.core import Brand
    from packages.db.models.media_jobs import MediaJob

    storage = get_storage()

    with _get_session() as session:
        # ── 1. Load records ──────────────────────────────────────────
        media_job = session.get(MediaJob, uuid.UUID(media_job_id))
        if not media_job:
            raise ValueError(f"MediaJob {media_job_id} not found")

        content_item = session.get(ContentItem, uuid.UUID(content_item_id))
        if not content_item:
            raise ValueError(f"ContentItem {content_item_id} not found")

        brand = session.get(Brand, content_item.brand_id)
        org_id = brand.organization_id if brand else media_job.org_id

        logger.info(
            "pipeline.continue",
            media_job_id=media_job_id,
            content_item_id=content_item_id,
            job_type=job_type,
            has_output_url=bool(output_url),
        )

        # ── 2. Persist output to durable storage ─────────────────────
        persistent_url = None
        if output_url:
            storage_key = storage.generate_key(
                prefix=_storage_prefix_for_job_type(job_type),
                extension=_extension_for_type(job_type),
            )
            persistent_url = storage.upload_from_url(output_url, key=storage_key)
            logger.info("pipeline.stored", key=storage_key, persistent_url=persistent_url)
        elif media_job.output_url:
            # Already have a URL on the job — persist that
            storage_key = storage.generate_key(
                prefix=_storage_prefix_for_job_type(job_type),
                extension=_extension_for_type(job_type),
            )
            persistent_url = storage.upload_from_url(media_job.output_url, key=storage_key)
        else:
            logger.warning(
                "pipeline.no_output_url",
                media_job_id=media_job_id,
                job_type=job_type,
            )

        # ── 3. Create / update Asset record ──────────────────────────
        asset = None
        if persistent_url:
            asset = Asset(
                brand_id=content_item.brand_id,
                content_item_id=content_item.id,
                asset_type=job_type,
                file_path=persistent_url,
                mime_type=_mime_for_job_type(job_type),
                storage_provider="s3" if storage.is_cloud else "local",
                metadata_blob={
                    "media_job_id": media_job_id,
                    "provider": media_job.provider,
                    "job_type": job_type,
                    "original_url": output_url or media_job.output_url,
                },
            )
            session.add(asset)
            session.flush()

            # Link asset to content item based on type
            if job_type in ("avatar", "video"):
                content_item.video_asset_id = asset.id

        # ── 4. Determine and dispatch next pipeline stage ────────────
        next_action = _dispatch_next_stage(
            session=session,
            job_type=job_type,
            content_item=content_item,
            media_job=media_job,
            org_id=org_id,
        )

        # ── 5. Emit pipeline event ───────────────────────────────────
        emit_event_sync(
            session,
            domain="pipeline",
            event_type="pipeline.step_completed",
            summary=f"Pipeline step completed: {job_type} for content {content_item_id}",
            org_id=org_id,
            brand_id=content_item.brand_id,
            entity_type="content_item",
            entity_id=content_item.id,
            previous_state=job_type,
            new_state=next_action.get("next_step", "unknown"),
            severity="info",
            actor_type="worker",
            actor_id="pipeline_worker",
            details={
                "media_job_id": media_job_id,
                "job_type": job_type,
                "persistent_url": persistent_url,
                "asset_id": str(asset.id) if asset else None,
                "next_action": next_action,
            },
        )

        session.commit()

        return {
            "status": "continued",
            "media_job_id": media_job_id,
            "content_item_id": content_item_id,
            "job_type": job_type,
            "persistent_url": persistent_url,
            "asset_id": str(asset.id) if asset else None,
            "next_action": next_action,
        }


def _extension_for_type(job_type: str) -> str:
    """Return file extension for a job type."""
    mapping = {
        "voice": "mp3",
        "avatar": "mp4",
        "video": "mp4",
        "image": "png",
        "music": "mp3",
        "b_roll": "mp4",
    }
    return mapping.get(job_type, "bin")


def _dispatch_next_stage(
    session: Session,
    job_type: str,
    content_item: object,
    media_job: object,
    org_id: uuid.UUID | None,
) -> dict:
    """Based on the completed job_type, determine and dispatch the next pipeline stage.

    Pipeline flow:
        voice completed   -> dispatch avatar generation
        avatar completed  -> dispatch b-roll if needed, otherwise assemble
        video/image/b_roll/music completed -> assemble_and_finalize

    Returns:
        Dict describing the next action taken.
    """
    from packages.db.models.media_jobs import MediaJob

    if job_type == "voice":
        # Voice done -> generate avatar video
        next_job = MediaJob(
            org_id=org_id or media_job.org_id,
            brand_id=content_item.brand_id,
            content_item_id=content_item.id,
            script_id=media_job.script_id,
            job_type="avatar",
            provider=media_job.provider,
            quality_tier=media_job.quality_tier,
            status="dispatched",
            dispatched_at=datetime.now(timezone.utc),
            input_payload={
                "voice_media_job_id": str(media_job.id),
                "content_item_id": str(content_item.id),
                "script_id": str(media_job.script_id) if media_job.script_id else None,
            },
            next_pipeline_task="workers.pipeline_worker.tasks.continue_pipeline",
            next_pipeline_args={
                "content_item_id": str(content_item.id),
                "job_type": "avatar",
            },
        )
        session.add(next_job)
        session.flush()

        content_item.status = "avatar_generating"

        logger.info(
            "pipeline.dispatch_avatar",
            content_item_id=str(content_item.id),
            next_media_job_id=str(next_job.id),
        )

        return {
            "next_step": "avatar",
            "dispatched_media_job_id": str(next_job.id),
            "description": "Avatar generation dispatched",
        }

    elif job_type == "avatar":
        # Avatar done -> check if b-roll is needed, otherwise go to assembly
        needs_broll = _content_needs_broll(content_item)

        if needs_broll:
            next_job = MediaJob(
                org_id=org_id or media_job.org_id,
                brand_id=content_item.brand_id,
                content_item_id=content_item.id,
                script_id=media_job.script_id,
                job_type="b_roll",
                provider=media_job.provider,
                quality_tier=media_job.quality_tier,
                status="dispatched",
                dispatched_at=datetime.now(timezone.utc),
                input_payload={
                    "avatar_media_job_id": str(media_job.id),
                    "content_item_id": str(content_item.id),
                },
                next_pipeline_task="workers.pipeline_worker.tasks.continue_pipeline",
                next_pipeline_args={
                    "content_item_id": str(content_item.id),
                    "job_type": "b_roll",
                },
            )
            session.add(next_job)
            session.flush()

            content_item.status = "broll_generating"

            logger.info(
                "pipeline.dispatch_broll",
                content_item_id=str(content_item.id),
                next_media_job_id=str(next_job.id),
            )

            return {
                "next_step": "b_roll",
                "dispatched_media_job_id": str(next_job.id),
                "description": "B-roll generation dispatched",
            }
        else:
            # No b-roll needed — go straight to assembly
            assemble_and_finalize.delay(str(content_item.id))

            content_item.status = "assembling"

            return {
                "next_step": "assemble",
                "description": "No b-roll needed, assembly dispatched",
            }

    else:
        # video, image, b_roll, music — all terminal media types -> assemble
        assemble_and_finalize.delay(str(content_item.id))

        content_item.status = "assembling"

        return {
            "next_step": "assemble",
            "description": f"{job_type} completed, assembly dispatched",
        }


def _content_needs_broll(content_item: object) -> bool:
    """Determine whether a content item should have b-roll generated.

    Heuristic: long-form video content benefits from b-roll.
    Short-form content (reels, shorts) typically doesn't need it.
    """
    ct = getattr(content_item, "content_type", None)
    if ct is None:
        return False

    ct_value = ct.value if hasattr(ct, "value") else str(ct)
    long_form_types = ("LONG_VIDEO", "TUTORIAL", "DOCUMENTARY", "COURSE_VIDEO")
    return ct_value.upper() in long_form_types


# ---------------------------------------------------------------------------
# assemble_and_finalize — gather all assets and mark ready to publish
# ---------------------------------------------------------------------------


@app.task(
    base=TrackedTask,
    bind=True,
    name="workers.pipeline_worker.tasks.assemble_and_finalize",
)
def assemble_and_finalize(self, content_item_id: str) -> dict:
    """Gather all completed media assets for a content item and finalize it.

    Steps:
        1. Load all completed MediaJobs for this content item.
        2. Build an asset manifest from persistent storage URLs.
        3. Update ContentItem status to 'ready_to_publish'.
        4. Dispatch to the publishing queue.
        5. Emit a pipeline.content_ready event.

    Args:
        content_item_id: UUID of the ContentItem to finalize.

    Returns:
        Dict with manifest, content status, and publishing dispatch result.
    """
    from apps.api.services.event_bus import emit_event_sync
    from packages.db.models.content import Asset, ContentItem
    from packages.db.models.core import Brand
    from packages.db.models.media_jobs import MediaJob

    with _get_session() as session:
        # ── 1. Load content item ─────────────────────────────────────
        content_item = session.get(ContentItem, uuid.UUID(content_item_id))
        if not content_item:
            raise ValueError(f"ContentItem {content_item_id} not found")

        brand = session.get(Brand, content_item.brand_id)
        org_id = brand.organization_id if brand else None

        logger.info("pipeline.assemble_start", content_item_id=content_item_id)

        # ── 2. Gather completed media jobs ───────────────────────────
        completed_jobs = (
            session.execute(
                select(MediaJob).where(
                    MediaJob.content_item_id == uuid.UUID(content_item_id),
                    MediaJob.status == "completed",
                )
            )
            .scalars()
            .all()
        )

        # ── 3. Gather associated assets ──────────────────────────────
        assets = (
            session.execute(
                select(Asset).where(
                    Asset.content_item_id == uuid.UUID(content_item_id),
                )
            )
            .scalars()
            .all()
        )

        # ── 4. Build asset manifest ──────────────────────────────────
        manifest = {
            "content_item_id": content_item_id,
            "assembled_at": datetime.now(timezone.utc).isoformat(),
            "media_jobs": [],
            "assets": [],
        }

        for job in completed_jobs:
            manifest["media_jobs"].append({
                "id": str(job.id),
                "job_type": job.job_type,
                "provider": job.provider,
                "output_url": job.output_url,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            })

        for asset in assets:
            manifest["assets"].append({
                "id": str(asset.id),
                "asset_type": asset.asset_type,
                "file_path": asset.file_path,
                "mime_type": asset.mime_type,
                "storage_provider": asset.storage_provider,
            })

        # ── 5. Update content item to ready_to_publish ───────────────
        content_item.status = "ready_to_publish"
        session.flush()

        logger.info(
            "pipeline.assemble_complete",
            content_item_id=content_item_id,
            job_count=len(completed_jobs),
            asset_count=len(assets),
        )

        # ── 6. Dispatch to publishing queue ──────────────────────────
        publish_dispatched = False
        try:
            from workers.publishing_worker.tasks import publish_content
            publish_content.delay(content_item_id)
            publish_dispatched = True
            logger.info("pipeline.publish_dispatched", content_item_id=content_item_id)
        except Exception:
            logger.warning(
                "pipeline.publish_dispatch_failed",
                content_item_id=content_item_id,
                exc_info=True,
            )

        # ── 7. Emit pipeline.content_ready event ─────────────────────
        emit_event_sync(
            session,
            domain="pipeline",
            event_type="pipeline.content_ready",
            summary=f"Content ready to publish: {content_item.title}",
            org_id=org_id,
            brand_id=content_item.brand_id,
            entity_type="content_item",
            entity_id=content_item.id,
            previous_state="assembling",
            new_state="ready_to_publish",
            severity="info",
            actor_type="worker",
            actor_id="pipeline_worker",
            details={
                "manifest": manifest,
                "publish_dispatched": publish_dispatched,
                "job_count": len(completed_jobs),
                "asset_count": len(assets),
            },
        )

        session.commit()

        return {
            "status": "ready_to_publish",
            "content_item_id": content_item_id,
            "title": content_item.title,
            "manifest": manifest,
            "publish_dispatched": publish_dispatched,
        }
