"""Publishing worker tasks — scheduling and platform publishing."""
import uuid
from datetime import datetime, timezone

from workers.celery_app import app
from workers.base_task import TrackedTask


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

        # Platform API integration point:
        # adapter = get_platform_adapter(job.platform)
        # result = adapter.publish(content_item, asset, account)
        # job.external_post_id = result.post_id
        # job.external_url = result.url

        job.status = JobStatus.COMPLETED
        job.published_at = datetime.now(timezone.utc)
        job.error_message = None

        if job.content_item_id:
            content = session.get(ContentItem, job.content_item_id)
            if content:
                content.status = "published"

        session.commit()

        return {
            "publish_job_id": str(job.id),
            "status": "published",
            "platform": job.platform.value,
            "published_at": job.published_at.isoformat() if job.published_at else None,
        }
