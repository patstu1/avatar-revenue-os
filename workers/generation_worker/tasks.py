"""Content generation worker tasks."""
import uuid

from workers.celery_app import app
from workers.base_task import TrackedTask


@app.task(base=TrackedTask, bind=True, name="workers.generation_worker.generate_script")
def generate_script(self, brief_id: str, brand_id: str) -> dict:
    """Generate a script from a content brief. Delegates to script generation service."""
    from sqlalchemy.orm import Session
    from packages.db.session import get_sync_engine
    from packages.db.models.content import ContentBrief, Script

    engine = get_sync_engine()
    with Session(engine) as session:
        brief = session.get(ContentBrief, uuid.UUID(brief_id))
        if not brief:
            raise ValueError(f"Brief {brief_id} not found")

        script = Script(
            brief_id=brief.id,
            brand_id=uuid.UUID(brand_id),
            title=f"Script for: {brief.title}",
            body_text="[Pending generation — requires AI provider credentials]",
            full_script="[Pending generation — requires AI provider credentials]",
            status="pending_generation",
            generation_model="pending",
        )
        session.add(script)
        session.commit()
        session.refresh(script)

        return {"script_id": str(script.id), "status": "created_pending_generation"}


@app.task(base=TrackedTask, bind=True, name="workers.generation_worker.generate_media")
def generate_media(self, script_id: str, avatar_id: str) -> dict:
    """Generate media (video/audio) from a script. Routes to provider based on capabilities."""
    from sqlalchemy.orm import Session
    from packages.db.session import get_sync_engine
    from packages.db.models.content import MediaJob
    from packages.db.enums import JobStatus

    engine = get_sync_engine()
    with Session(engine) as session:
        media_job = MediaJob(
            brand_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            script_id=uuid.UUID(script_id),
            avatar_id=uuid.UUID(avatar_id),
            job_type="avatar_video",
            status=JobStatus.PENDING,
            provider="pending_routing",
        )
        session.add(media_job)
        session.commit()
        session.refresh(media_job)

        return {"media_job_id": str(media_job.id), "status": "created_pending_provider"}
