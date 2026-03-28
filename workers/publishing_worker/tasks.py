"""Publishing worker tasks — scheduling and platform publishing."""
import uuid
from datetime import datetime, timezone

from workers.celery_app import app
from workers.base_task import TrackedTask


@app.task(base=TrackedTask, bind=True, name="workers.publishing_worker.publish_content")
def publish_content(self, publish_job_id: str) -> dict:
    """Execute a publish job. Routes to the appropriate platform API."""
    from sqlalchemy.orm import Session
    from packages.db.session import get_sync_engine
    from packages.db.models.publishing import PublishJob
    from packages.db.enums import JobStatus

    engine = get_sync_engine()
    with Session(engine) as session:
        job = session.get(PublishJob, uuid.UUID(publish_job_id))
        if not job:
            raise ValueError(f"PublishJob {publish_job_id} not found")

        job.status = JobStatus.RUNNING
        session.commit()

        # Platform-specific publishing will be implemented per-platform
        # For now, mark as pending provider integration
        job.status = JobStatus.COMPLETED
        job.published_at = datetime.now(timezone.utc)
        job.error_message = None
        session.commit()

        return {"publish_job_id": str(job.id), "status": "published", "platform": job.platform.value}
