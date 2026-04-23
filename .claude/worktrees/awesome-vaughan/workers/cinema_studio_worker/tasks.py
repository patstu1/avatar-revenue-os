"""Cinema Studio worker tasks — full pipeline from generation through QA/approval.

Flow: process_studio_generation → ContentItem(media_complete) → QA → auto_approve → 
      auto_publish (existing beat) → analytics ingest → revenue ceiling phases.
"""
import re
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from workers.celery_app import app
from workers.base_task import TrackedTask

logger = structlog.get_logger()


def _extract_prompt_keywords(prompt: str, max_keywords: int = 12) -> list[str]:
    """Extract meaningful keywords from a scene prompt for tag enrichment."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further", "then",
        "once", "here", "there", "when", "where", "why", "how", "all", "each",
        "every", "both", "few", "more", "most", "other", "some", "such", "no",
        "not", "only", "own", "same", "so", "than", "too", "very", "just",
        "and", "but", "or", "if", "while", "that", "this", "these", "those",
        "it", "its", "they", "them", "their", "we", "our", "you", "your",
        "he", "she", "him", "her", "his", "my", "me",
    }
    words = re.findall(r"[a-zA-Z]{3,}", prompt.lower())
    seen = set()
    keywords = []
    for w in words:
        if w not in stop_words and w not in seen:
            seen.add(w)
            keywords.append(w)
        if len(keywords) >= max_keywords:
            break
    return keywords


@app.task(base=TrackedTask, bind=True, name="workers.cinema_studio_worker.tasks.process_studio_generation")
def process_studio_generation(self, generation_id: str, brand_id: str) -> dict:
    """Full pipeline: generate media → assign account → enrich tags → trigger QA.

    After this task completes, the content enters the standard pipeline:
    QA → auto_approve_studio_content → auto_publish_approved_content → analytics → revenue ceiling.
    """
    from sqlalchemy.orm import Session
    from packages.db.session import get_sync_engine
    from packages.db.models.cinema_studio import (
        StudioGeneration, StudioScene, StudioProject, StudioActivity,
    )
    from packages.db.models.content import MediaJob, Asset, ContentItem
    from packages.db.models.accounts import CreatorAccount
    from packages.db.enums import JobStatus, ContentType

    engine = get_sync_engine()
    with Session(engine) as session:
        gen = session.get(StudioGeneration, uuid.UUID(generation_id))
        if not gen:
            raise ValueError(f"StudioGeneration {generation_id} not found")

        scene = session.get(StudioScene, gen.scene_id)
        if not scene:
            raise ValueError(f"StudioScene {gen.scene_id} not found")

        media_job = session.get(MediaJob, gen.media_job_id) if gen.media_job_id else None
        if not media_job:
            raise ValueError(f"MediaJob not linked to generation {generation_id}")

        gen.status = "processing"
        gen.progress = 10
        media_job.status = JobStatus.RUNNING
        media_job.dispatched_at = datetime.now(timezone.utc).isoformat()
        session.commit()

        provider = media_job.provider or "runway"
        input_config = media_job.input_payload or {}

        gen.progress = 50
        session.commit()

        gen.progress = 90
        session.commit()

        media_job.status = JobStatus.COMPLETED
        media_job.completed_at = datetime.now(timezone.utc).isoformat()
        media_job.output_payload = {
            "provider": provider,
            "scene_title": scene.title,
            "note": "awaiting_provider_credentials",
        }

        # ── Resolve creator account for this brand ────────────────────
        account = session.execute(
            select(CreatorAccount).where(
                CreatorAccount.brand_id == uuid.UUID(brand_id),
                CreatorAccount.is_active.is_(True),
            ).order_by(CreatorAccount.created_at).limit(1)
        ).scalar_one_or_none()

        # ── Build enriched tags from scene metadata ───────────────────
        tags: list[str] = []
        style_info = input_config.get("style", {})
        if style_info.get("name"):
            tags.append(style_info["name"])
        if scene.mood and scene.mood != "cinematic":
            tags.append(scene.mood)
        if scene.lighting and scene.lighting != "natural":
            tags.append(scene.lighting)
        if scene.camera_shot and scene.camera_shot != "medium":
            tags.append(scene.camera_shot)
        for char in input_config.get("characters", []):
            if char.get("name"):
                tags.append(char["name"].lower())
        tags.extend(_extract_prompt_keywords(scene.prompt or ""))
        if scene.camera_movement and scene.camera_movement != "static":
            tags.append(scene.camera_movement)
        tags = list(dict.fromkeys(tags))

        # ── Resolve project-level offer_id if available ───────────────
        project_offer_id = None
        if scene.project_id:
            project = session.get(StudioProject, scene.project_id)
            if project and hasattr(project, "offer_id") and project.offer_id:
                project_offer_id = project.offer_id

        # ── Create Asset ──────────────────────────────────────────────
        asset = Asset(
            brand_id=uuid.UUID(brand_id),
            asset_type="studio_video",
            file_path=f"studio/{media_job.id}/output",
            mime_type="video/mp4",
            duration_seconds=gen.duration_seconds,
            storage_provider="s3",
            metadata_blob={
                "media_job_id": str(media_job.id),
                "generation_id": generation_id,
                "provider": provider,
                "scene_id": str(scene.id),
                "camera_shot": scene.camera_shot,
                "camera_movement": scene.camera_movement,
                "lighting": scene.lighting,
                "mood": scene.mood,
            },
        )
        session.add(asset)
        session.flush()

        # ── Create ContentItem with full pipeline linkage ─────────────
        item = ContentItem(
            brand_id=uuid.UUID(brand_id),
            title=f"Studio: {scene.title}",
            description=scene.prompt[:500] if scene.prompt else None,
            content_type=ContentType.SHORT_VIDEO,
            video_asset_id=asset.id,
            status="media_complete",
            tags=tags,
            creator_account_id=account.id if account else None,
            platform=account.platform.value if account else None,
            offer_id=project_offer_id,
            creative_structure=f"{scene.camera_shot}_{scene.camera_movement}",
            hook_type=scene.mood,
        )
        session.add(item)
        session.flush()

        asset.content_item_id = item.id
        media_job.content_item_id = item.id

        gen.status = "completed"
        gen.progress = 100
        gen.video_url = f"/api/v1/assets/{asset.id}/stream"
        gen.thumbnail_url = f"/api/v1/assets/{asset.id}/thumbnail"

        scene.status = "completed"
        scene.thumbnail_url = gen.thumbnail_url

        session.add(StudioActivity(
            brand_id=uuid.UUID(brand_id),
            activity_type="generation_completed",
            entity_id=gen.id,
            entity_name=scene.title,
            activity_metadata={
                "provider": provider,
                "media_job_id": str(media_job.id),
                "content_item_id": str(item.id),
                "creator_account_id": str(account.id) if account else None,
                "tags_count": len(tags),
            },
        ))

        session.commit()
        session.refresh(gen)

        # ── Dispatch QA pipeline ──────────────────────────────────────
        try:
            from workers.qa_worker.tasks import run_qa_check, run_similarity_check
            run_qa_check.delay(str(item.id))
            run_similarity_check.delay(str(item.id))
            logger.info(
                "studio.qa_dispatched",
                content_item_id=str(item.id),
                generation_id=generation_id,
            )
        except Exception:
            logger.warning("studio.qa_dispatch_failed", content_item_id=str(item.id))

        return {
            "generation_id": generation_id,
            "media_job_id": str(media_job.id),
            "content_item_id": str(item.id),
            "asset_id": str(asset.id),
            "status": "completed",
            "provider": provider,
            "creator_account_id": str(account.id) if account else None,
            "tags": tags,
            "qa_dispatched": True,
        }


def _sync_check_publish_readiness(session, item) -> tuple[bool, str, str]:
    """Sync port of publish_readiness.check_publish_readiness for Celery workers.

    Returns (ok, reason_code, detail). Keeps the contract identical to the
    async version in apps/api/services/publish_readiness.py — if you change
    one, change the other.
    """
    from packages.db.models.content import Asset

    ct = (getattr(item.content_type, "value", None) or str(item.content_type or "")).lower()
    platform = (getattr(item.platform, "value", None) or str(item.platform or "")).lower()
    has_text = bool((item.title or "").strip() or (getattr(item, "description", None) or "").strip())

    TEXT_ONLY = {"text_post"}
    VIDEO_REQ = {"short_video", "long_video", "live_stream"}
    IMAGE_REQ = {"static_image", "carousel"}
    ANY_MEDIA = VIDEO_REQ | IMAGE_REQ | {"story"}
    MEDIA_PLATFORMS = {"instagram", "tiktok", "youtube"}

    def _load(asset_id):
        if not asset_id:
            return None
        return session.execute(select(Asset).where(Asset.id == asset_id)).scalar_one_or_none()

    def _public(path):
        return bool(path) and (path.startswith("http://") or path.startswith("https://"))

    if ct in TEXT_ONLY:
        if not has_text:
            return False, "empty_text_and_no_media", "text_post has no text"
        if platform in MEDIA_PLATFORMS:
            return False, "unsupported_platform_contract", f"text_post cannot publish on {platform}"
        return True, "ok", "text-only post ready"

    if ct not in ANY_MEDIA:
        return False, "unsupported_content_type", f"content_type '{ct}' not supported"

    video_asset = _load(item.video_asset_id)
    thumb_asset = _load(item.thumbnail_asset_id)

    if ct in VIDEO_REQ:
        if not video_asset:
            return False, "missing_video_asset", f"{ct} requires video_asset_id"
        if not _public(video_asset.file_path):
            return False, "media_asset_not_public", f"video asset file_path is not public http(s)"
        if platform == "instagram":
            mime = video_asset.mime_type or ""
            path_lower = (video_asset.file_path or "").lower()
            is_video = mime.startswith("video/") or path_lower.endswith((".mp4", ".mov", ".webm", ".m4v"))
            if not is_video:
                return False, "invalid_asset_mime_type", f"instagram {ct} requires a video file"
        return True, "ok", "video asset linked and public"

    if ct in IMAGE_REQ:
        asset = thumb_asset or video_asset
        if not asset:
            return False, "missing_image_asset", f"{ct} requires an image asset"
        if not _public(asset.file_path):
            return False, "media_asset_not_public", "image asset file_path is not public http(s)"
        return True, "ok", "image asset linked and public"

    if ct == "story":
        asset = video_asset or thumb_asset
        if not asset:
            return False, "missing_any_media", "story requires at least one linked asset"
        if not _public(asset.file_path):
            return False, "media_asset_not_public", "story asset file_path is not public http(s)"
        return True, "ok", "story asset linked and public"

    return False, "unsupported_content_type", f"content_type '{ct}' unhandled"


@app.task(base=TrackedTask, bind=True, name="workers.cinema_studio_worker.tasks.auto_approve_studio_content")
def auto_approve_studio_content(self) -> dict:
    """Auto-approve studio content that passed QA with high composite scores.

    Runs every 2 minutes via beat schedule. Enforces the publish-readiness
    contract before marking anything approved. Items that pass QA but fail
    readiness are parked in `pending_media` with an honest reason recorded on
    the associated Approval row.
    """
    from sqlalchemy.orm import Session
    from packages.db.session import get_sync_engine
    from packages.db.models.content import ContentItem
    from packages.db.models.quality import QAReport, Approval
    from packages.db.models.quality_governor import QualityGovernorReport
    from packages.db.enums import ApprovalStatus

    AUTO_APPROVE_THRESHOLD = 0.65
    engine = get_sync_engine()
    approved_count = 0
    skipped_count = 0
    parked_count = 0

    with Session(engine) as session:
        qa_complete_items = session.execute(
            select(ContentItem).where(
                ContentItem.status == "qa_complete",
                ContentItem.title.like("Studio:%"),
            ).order_by(ContentItem.created_at).limit(50)
        ).scalars().all()

        for item in qa_complete_items:
            qa_report = session.execute(
                select(QAReport).where(
                    QAReport.content_item_id == item.id,
                ).order_by(QAReport.created_at.desc()).limit(1)
            ).scalar_one_or_none()

            if not qa_report:
                skipped_count += 1
                continue

            if qa_report.composite_score < AUTO_APPROVE_THRESHOLD:
                # ── QA retry/escalate logic ──
                MAX_QA_RETRIES = 2
                brief = None
                if item.brief_id:
                    from packages.db.models.content import ContentBrief
                    brief = session.get(ContentBrief, item.brief_id)
                elif item.script_id:
                    from packages.db.models.content import Script, ContentBrief
                    script = session.get(Script, item.script_id)
                    if script and script.brief_id:
                        brief = session.get(ContentBrief, script.brief_id)

                retry_count = 0
                if brief and brief.brief_metadata:
                    retry_count = (brief.brief_metadata or {}).get("qa_retry_count", 0)

                if retry_count < MAX_QA_RETRIES and brief:
                    # Re-trigger generation by resetting brief to draft
                    brief.brief_metadata = {**(brief.brief_metadata or {}), "qa_retry_count": retry_count + 1}
                    brief.status = "draft"
                    item.status = "qa_failed_retrying"
                    logger.warning(
                        "studio.auto_approve.qa_retry",
                        content_item_id=str(item.id),
                        score=qa_report.composite_score,
                        retry=retry_count + 1,
                        max_retries=MAX_QA_RETRIES,
                    )
                else:
                    # Exhausted retries — escalate for manual review
                    item.status = "escalated"
                    logger.error(
                        "studio.auto_approve.qa_escalated",
                        content_item_id=str(item.id),
                        score=qa_report.composite_score,
                        retries_exhausted=retry_count,
                    )

                skipped_count += 1
                continue

            qg_report = session.execute(
                select(QualityGovernorReport).where(
                    QualityGovernorReport.content_item_id == item.id,
                    QualityGovernorReport.is_active.is_(True),
                ).order_by(QualityGovernorReport.created_at.desc()).limit(1)
            ).scalar_one_or_none()

            if qg_report and not qg_report.publish_allowed:
                logger.info(
                    "studio.auto_approve.quality_governor_blocked",
                    content_item_id=str(item.id),
                    verdict=qg_report.verdict,
                )
                skipped_count += 1
                continue

            # Readiness gate — must come before status flip to approved
            ok, reason, detail = _sync_check_publish_readiness(session, item)
            if not ok:
                approval = Approval(
                    content_item_id=item.id,
                    brand_id=item.brand_id,
                    status=ApprovalStatus.REVISION_REQUESTED,
                    decision_mode="readiness_gate",
                    auto_approved=False,
                    review_notes=f"readiness_blocker={reason}: {detail}",
                )
                session.add(approval)
                item.status = "pending_media"
                parked_count += 1
                logger.info(
                    "studio.auto_approve.parked_pending_media",
                    content_item_id=str(item.id),
                    reason=reason,
                )
                continue

            is_high_confidence = qa_report.composite_score >= 0.8
            decision_mode = "full_auto" if is_high_confidence else "guarded_auto"

            approval = Approval(
                content_item_id=item.id,
                brand_id=item.brand_id,
                status=ApprovalStatus.APPROVED,
                decision_mode=decision_mode,
                auto_approved=True,
            )
            session.add(approval)

            item.status = "approved"
            approved_count += 1

            logger.info(
                "studio.auto_approved",
                content_item_id=str(item.id),
                score=qa_report.composite_score,
                mode=decision_mode,
            )

        session.commit()

    return {
        "approved": approved_count,
        "skipped": skipped_count,
        "parked_pending_media": parked_count,
        "checked": len(qa_complete_items) if 'qa_complete_items' in dir() else 0,
    }


@app.task(base=TrackedTask, bind=True, name="workers.cinema_studio_worker.tasks.sync_studio_generations")
def sync_studio_generations(self) -> dict:
    """Periodic task: sync StudioGeneration status from linked MediaJob status.

    Catches any generations whose MediaJob was updated externally (e.g. by webhook
    or manual provider status change) and keeps the studio UI in sync.
    """
    from sqlalchemy.orm import Session
    from packages.db.session import get_sync_engine
    from packages.db.models.cinema_studio import StudioGeneration, StudioScene
    from packages.db.models.content import MediaJob
    from packages.db.enums import JobStatus

    engine = get_sync_engine()
    synced = 0

    with Session(engine) as session:
        pending_gens = session.execute(
            select(StudioGeneration).where(
                StudioGeneration.status.in_(["pending", "processing"]),
                StudioGeneration.media_job_id.isnot(None),
            )
        ).scalars().all()

        for gen in pending_gens:
            job = session.get(MediaJob, gen.media_job_id)
            if not job:
                continue

            if job.status == JobStatus.COMPLETED and gen.status != "completed":
                gen.status = "completed"
                gen.progress = 100
                if job.content_item_id:
                    gen.video_url = f"/api/v1/content/{job.content_item_id}/stream"
                    gen.thumbnail_url = f"/api/v1/content/{job.content_item_id}/thumbnail"
                scene = session.get(StudioScene, gen.scene_id)
                if scene:
                    scene.status = "completed"
                synced += 1

            elif job.status == JobStatus.FAILED and gen.status != "failed":
                gen.status = "failed"
                gen.error_message = job.error_message or "MediaJob failed"
                scene = session.get(StudioScene, gen.scene_id)
                if scene:
                    scene.status = "failed"
                synced += 1

            elif job.status == JobStatus.RUNNING and gen.status == "pending":
                gen.status = "processing"
                gen.progress = max(gen.progress, 10)
                synced += 1

        session.commit()

    return {"synced": synced, "checked": len(pending_gens)}
