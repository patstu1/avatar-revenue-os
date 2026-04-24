"""Content pipeline endpoints — Phase 3 core.

Now integrated with the content lifecycle service for event emission,
quality gates, and operator action generation. The existing pipeline
service handles business logic; the lifecycle service adds coordination.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.schemas.content_pipeline import (
    ApprovalAction,
    ApprovalResponse,
    BriefResponse,
    BriefUpdate,
    ContentItemResponse,
    MediaJobResponse,
    PublishJobResponse,
    QAReportResponse,
    ScheduleRequest,
    ScriptResponse,
    ScriptUpdate,
    SimilarityReportResponse,
)
from apps.api.services import content_lifecycle as lifecycle
from apps.api.services import content_pipeline_service as cps
from apps.api.services.audit_service import log_action
from packages.db.models.content import ContentBrief, ContentItem, MediaJob, Script
from packages.db.models.quality import Approval

router = APIRouter()


@router.get("/briefs/{brief_id}", response_model=BriefResponse)
async def get_brief(brief_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        return await cps.get_brief(db, brief_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/briefs/{brief_id}", response_model=BriefResponse)
async def update_brief(brief_id: uuid.UUID, body: BriefUpdate, current_user: OperatorUser, db: DBSession):
    try:
        brief = await cps.update_brief(db, brief_id, **body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await log_action(db, "brief.updated", organization_id=current_user.organization_id,
                     brand_id=brief.brand_id, user_id=current_user.id, actor_type="human",
                     entity_type="content_brief", entity_id=brief_id)
    return brief


@router.post("/briefs/{brief_id}/generate-scripts", response_model=ScriptResponse)
async def generate_scripts(brief_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    try:
        script = await lifecycle.generate_script_with_events(
            db, brief_id, actor_id=str(current_user.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await log_action(db, "script.generated", organization_id=current_user.organization_id,
                     brand_id=script.brand_id, user_id=current_user.id, actor_type="human",
                     entity_type="script", entity_id=script.id)
    return script


@router.get("/scripts/{script_id}", response_model=ScriptResponse)
async def get_script(script_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        return await cps.get_script(db, script_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/scripts/{script_id}", response_model=ScriptResponse)
async def update_script(script_id: uuid.UUID, body: ScriptUpdate, current_user: OperatorUser, db: DBSession):
    try:
        script = await cps.update_script(db, script_id, **body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await log_action(db, "script.updated", organization_id=current_user.organization_id,
                     brand_id=script.brand_id, user_id=current_user.id, actor_type="human",
                     entity_type="script", entity_id=script_id)
    return script


@router.post("/scripts/{script_id}/score")
async def score_script(script_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        return await cps.score_script(db, script_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/scripts/{script_id}/generate-media", response_model=MediaJobResponse)
async def generate_media(script_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    try:
        job = await cps.generate_media(db, script_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await log_action(db, "media_job.created", organization_id=current_user.organization_id,
                     brand_id=job.brand_id, user_id=current_user.id, actor_type="human",
                     entity_type="media_job", entity_id=job.id)
    return job


@router.get("/media-jobs/{job_id}", response_model=MediaJobResponse)
async def get_media_job(job_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        return await cps.get_media_job(db, job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/media-jobs/{job_id}/finalize", response_model=ContentItemResponse)
async def finalize_media(job_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    """Bridge a completed MediaJob into a ContentItem for QA/approval/publish."""
    try:
        item = await lifecycle.finalize_media_with_events(db, job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await log_action(db, "content_item.created_from_media", organization_id=current_user.organization_id,
                     brand_id=item.brand_id, user_id=current_user.id, actor_type="human",
                     entity_type="content_item", entity_id=item.id)
    return item


@router.post("/content/{content_id}/run-qa")
async def run_qa(content_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    """Run QA with quality gate enforcement. May block content if quality is insufficient."""
    try:
        result = await lifecycle.run_qa_with_events(
            db, content_id, actor_id=str(current_user.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    report = result["qa_report"]
    await log_action(db, "qa.completed", organization_id=current_user.organization_id,
                     brand_id=report.brand_id, user_id=current_user.id, actor_type="system",
                     entity_type="qa_report", entity_id=report.id)
    return {
        "qa_report": QAReportResponse.model_validate(report),
        "quality_blocked": result["quality_blocked"],
        "blocking_reasons": result["blocking_reasons"],
    }


@router.get("/qa/{content_id}")
async def get_qa(content_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        result = await cps.get_qa_report(db, content_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")
    qa = result["qa_report"]
    sim = result["similarity_report"]
    return {
        "qa_report": QAReportResponse.model_validate(qa) if qa else None,
        "similarity_report": SimilarityReportResponse.model_validate(sim) if sim else None,
    }


@router.post("/content/{content_id}/approve", response_model=ApprovalResponse)
async def approve_content(content_id: uuid.UUID, body: ApprovalAction, current_user: OperatorUser, db: DBSession):
    try:
        result = await lifecycle.approve_with_events(db, content_id, current_user.id, body.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    approval = result["approval"]
    await log_action(db, "content.approved", organization_id=current_user.organization_id,
                     brand_id=approval.brand_id, user_id=current_user.id, actor_type="human",
                     entity_type="approval", entity_id=approval.id)
    return approval


@router.post("/content/{content_id}/reject", response_model=ApprovalResponse)
async def reject_content(content_id: uuid.UUID, body: ApprovalAction, current_user: OperatorUser, db: DBSession):
    try:
        result = await lifecycle.reject_with_events(db, content_id, current_user.id, body.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    approval = result["approval"]
    await log_action(db, "content.rejected", organization_id=current_user.organization_id,
                     brand_id=approval.brand_id, user_id=current_user.id, actor_type="human",
                     entity_type="approval", entity_id=approval.id)
    return approval


@router.post("/content/{content_id}/request-changes", response_model=ApprovalResponse)
async def request_changes(content_id: uuid.UUID, body: ApprovalAction, current_user: OperatorUser, db: DBSession):
    try:
        approval = await cps.request_changes(db, content_id, current_user.id, body.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await log_action(db, "content.changes_requested", organization_id=current_user.organization_id,
                     brand_id=approval.brand_id, user_id=current_user.id, actor_type="human",
                     entity_type="approval", entity_id=approval.id)
    return approval


@router.post("/content/{content_id}/schedule", response_model=PublishJobResponse)
async def schedule_content(content_id: uuid.UUID, body: ScheduleRequest, current_user: OperatorUser, db: DBSession):
    try:
        job = await cps.schedule_publish(db, content_id, body.creator_account_id, body.platform, body.scheduled_at)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await log_action(db, "content.scheduled", organization_id=current_user.organization_id,
                     user_id=current_user.id, actor_type="human",
                     entity_type="publish_job", entity_id=job.id)
    return job


@router.post("/content/{content_id}/publish-now", response_model=PublishJobResponse)
async def publish_now(content_id: uuid.UUID, body: ScheduleRequest, current_user: OperatorUser, db: DBSession):
    try:
        result = await lifecycle.publish_with_events(
            db, content_id, body.creator_account_id, body.platform,
            actor_id=str(current_user.id),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    job = result["job"]
    await log_action(db, "content.published", organization_id=current_user.organization_id,
                     user_id=current_user.id, actor_type="human",
                     entity_type="publish_job", entity_id=job.id)
    return job


@router.get("/content/{content_id}/publish-status", response_model=list[PublishJobResponse])
async def get_publish_status(content_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        return await cps.get_publish_status(db, content_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error processing request")


@router.get("/content/library", response_model=list[ContentItemResponse])
async def content_library(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession,
    status: Optional[str] = None, page: int = Query(1, ge=1),
):
    query = select(ContentItem).where(ContentItem.brand_id == brand_id)
    if status:
        query = query.where(ContentItem.status == status)
    query = query.order_by(ContentItem.created_at.desc()).offset((page - 1) * 50).limit(50)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/approvals/queue", response_model=list[ApprovalResponse])
async def approval_queue(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(Approval).where(Approval.brand_id == brand_id, Approval.status == "pending")
        .order_by(Approval.created_at.asc())
    )
    return list(result.scalars().all())


@router.get("/media-jobs", response_model=list[MediaJobResponse])
async def list_media_jobs(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession, page: int = Query(1, ge=1)):
    result = await db.execute(
        select(MediaJob).where(MediaJob.brand_id == brand_id)
        .order_by(MediaJob.created_at.desc()).offset((page - 1) * 50).limit(50)
    )
    return list(result.scalars().all())


@router.get("/scripts", response_model=list[ScriptResponse])
async def list_scripts(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession, page: int = Query(1, ge=1)):
    result = await db.execute(
        select(Script).where(Script.brand_id == brand_id)
        .order_by(Script.created_at.desc()).offset((page - 1) * 50).limit(50)
    )
    return list(result.scalars().all())


@router.get("/briefs", response_model=list[BriefResponse])
async def list_briefs(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession, page: int = Query(1, ge=1)):
    result = await db.execute(
        select(ContentBrief).where(ContentBrief.brand_id == brand_id)
        .order_by(ContentBrief.created_at.desc()).offset((page - 1) * 50).limit(50)
    )
    return list(result.scalars().all())


@router.delete("/content/{content_id}", status_code=204)
async def delete_content(content_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    item = await db.get(ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    await db.delete(item)
    await db.flush()
    await log_action(db, "content.deleted", organization_id=current_user.organization_id,
                     brand_id=item.brand_id, user_id=current_user.id, actor_type="human",
                     entity_type="content_item", entity_id=content_id)
