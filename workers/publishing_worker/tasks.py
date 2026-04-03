"""Publishing worker tasks — scheduling and platform publishing."""
import uuid
from datetime import datetime, timezone

from workers.celery_app import app
from workers.base_task import TrackedTask

import workers.publishing_worker.auto_publish  # noqa: F401
import workers.publishing_worker.measured_data_cascade  # noqa: F401


@app.task(base=TrackedTask, bind=True, name="workers.publishing_worker.publish_content")
def publish_content(self, publish_job_id: str) -> dict:
    """Execute a publish job. Routes to the appropriate platform API.

    When platform API credentials are configured, this task will call the
    real platform adapter (YouTube, TikTok, Instagram, etc.). Until then,
    it marks the job as completed and updates content status so the
    downstream analytics pipeline can track it.
    """
    from sqlalchemy.orm import Session
    from packages.db.session import get_sync_engine
    from packages.db.models.publishing import PublishJob
    from packages.db.models.content import ContentItem
    from packages.db.enums import JobStatus

    engine = get_sync_engine()
    with Session(engine) as session:
        job = session.get(PublishJob, uuid.UUID(publish_job_id))
        if not job:
            raise ValueError(f"PublishJob {publish_job_id} not found")

        from packages.db.models.quality_governor import QualityGovernorReport
        if job.content_item_id:
            qg = session.query(QualityGovernorReport).filter(
                QualityGovernorReport.content_item_id == job.content_item_id,
                QualityGovernorReport.is_active.is_(True),
            ).order_by(QualityGovernorReport.created_at.desc()).first()
            if qg and not qg.publish_allowed:
                job.status = JobStatus.FAILED
                job.error_message = f"Quality Governor blocked: {qg.verdict} (score={qg.total_score:.2f})"
                session.commit()
                return {"publish_job_id": publish_job_id, "status": "quality_blocked", "reason": job.error_message}

        from packages.db.models.workflow_builder import WorkflowInstance
        if job.content_item_id:
            wf_inst = session.query(WorkflowInstance).filter(
                WorkflowInstance.resource_type == "content_item",
                WorkflowInstance.resource_id == job.content_item_id,
                WorkflowInstance.is_active.is_(True),
            ).order_by(WorkflowInstance.created_at.desc()).first()
            if wf_inst and wf_inst.status == "in_progress":
                job.status = JobStatus.FAILED
                job.error_message = f"Workflow pending: step {wf_inst.current_step_order} awaiting approval"
                session.commit()
                return {"publish_job_id": publish_job_id, "status": "workflow_pending", "reason": job.error_message}

        job.status = JobStatus.RUNNING
        session.commit()

        content = session.get(ContentItem, job.content_item_id) if job.content_item_id else None
        publish_result = _try_buffer_publish(session, job, content)

        if publish_result.get("published"):
            job.status = JobStatus.COMPLETED
            job.published_at = datetime.now(timezone.utc)
            job.error_message = None
            job.platform_post_id = publish_result.get("buffer_post_id")
            job.platform_post_url = publish_result.get("url")
            if content:
                content.status = "published"
        elif publish_result.get("no_buffer"):
            job.status = JobStatus.FAILED
            job.error_message = publish_result.get("error", "No publishing channel configured")
        else:
            job.status = JobStatus.FAILED
            job.error_message = publish_result.get("error", "Publishing failed")
            job.retries = (job.retries or 0) + 1

        session.commit()

        return {
            "publish_job_id": str(job.id),
            "status": "published" if job.status == JobStatus.COMPLETED else "failed",
            "platform": job.platform.value if hasattr(job.platform, 'value') else str(job.platform),
            "published_at": job.published_at.isoformat() if job.published_at else None,
            "error": job.error_message,
        }


def _try_buffer_publish(session, job, content) -> dict:
    """Attempt to publish via Buffer. Returns result dict."""
    import asyncio
    import os
    from packages.db.models.buffer_distribution import BufferProfile

    buffer_key = os.environ.get("BUFFER_API_KEY", "")
    if not buffer_key:
        return {"no_buffer": True, "error": "BUFFER_API_KEY not configured. Add your Buffer API key in Settings > Integrations."}

    platform_val = job.platform.value if hasattr(job.platform, 'value') else str(job.platform)
    profile = session.query(BufferProfile).filter(
        BufferProfile.brand_id == job.brand_id,
        BufferProfile.platform == job.platform,
        BufferProfile.is_active.is_(True),
        BufferProfile.credential_status == "connected",
    ).first()

    if not profile or not profile.buffer_profile_id:
        return {"no_buffer": True, "error": f"No connected Buffer profile found for platform '{platform_val}'. Connect one in Buffer Distribution settings."}

    text = ""
    media = None
    if content:
        text = content.description or content.title or ""
        if hasattr(content, 'video_asset_id') and content.video_asset_id:
            from packages.db.models.content import Asset
            asset = session.get(Asset, content.video_asset_id)
            if asset and asset.file_path and asset.file_path.startswith("http"):
                media = {"video": asset.file_path}

    if not text:
        return {"error": "No content text available for publishing"}

    from packages.clients.external_clients import BufferClient
    client = BufferClient(api_key=buffer_key)

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            client.create_update(
                profile_ids=[profile.buffer_profile_id],
                text=text,
                media=media,
                scheduled_at=job.scheduled_at.isoformat() if job.scheduled_at else None,
            )
        )
        loop.close()
    except Exception as e:
        return {"error": f"Buffer API call failed: {e}"}

    if result.get("success"):
        updates = (result.get("data") or {}).get("updates", [{}])
        buffer_id = updates[0].get("id", "") if updates else ""
        return {"published": True, "buffer_post_id": buffer_id, "url": ""}
    elif result.get("blocked"):
        return {"no_buffer": True, "error": result.get("error", "Buffer API blocked")}
    else:
        return {"error": result.get("error", "Buffer publish failed")}
