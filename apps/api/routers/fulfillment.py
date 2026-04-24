"""Fulfillment router (Batch 3C) — projects, briefs, production jobs.

Operator-facing read + admin-control endpoints. The happy-path writes
happen automatically when an intake completes; these routes exist so
the operator can inspect state and manually retrigger/regenerate when
needed.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select

from apps.api.deps import DBSession, OperatorUser
from apps.api.services.fulfillment_service import (
    generate_brief_for_project,
    launch_production_for_brief,
)
from packages.db.models.fulfillment import (
    ClientProject,
    ProductionJob,
    ProjectBrief,
)

logger = structlog.get_logger()

router = APIRouter(tags=["Fulfillment"])


# ── Projects ────────────────────────────────────────────────────────────────


@router.get("/projects")
async def list_projects(
    current_user: OperatorUser,
    db: DBSession,
    status: str | None = None,
    limit: int = 50,
):
    q = select(ClientProject).where(
        ClientProject.org_id == current_user.organization_id,
        ClientProject.is_active.is_(True),
    )
    if status:
        q = q.where(ClientProject.status == status)
    q = q.order_by(desc(ClientProject.created_at)).limit(max(1, min(200, limit)))
    rows = (await db.execute(q)).scalars().all()
    return [_project_summary(p) for p in rows]


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    current_user: OperatorUser,
    db: DBSession,
):
    pid = _parse_uuid(project_id)
    project = await _require_owned_project(db, pid, current_user.organization_id)

    briefs = (
        (
            await db.execute(
                select(ProjectBrief).where(ProjectBrief.project_id == project.id).order_by(desc(ProjectBrief.version))
            )
        )
        .scalars()
        .all()
    )
    jobs = (
        (
            await db.execute(
                select(ProductionJob)
                .where(ProductionJob.project_id == project.id)
                .order_by(desc(ProductionJob.created_at))
            )
        )
        .scalars()
        .all()
    )

    return {
        **_project_summary(project),
        "client_id": str(project.client_id),
        "intake_submission_id": str(project.intake_submission_id) if project.intake_submission_id else None,
        "proposal_id": str(project.proposal_id) if project.proposal_id else None,
        "payment_id": str(project.payment_id) if project.payment_id else None,
        "description": project.description,
        "briefs": [_brief_summary(b) for b in briefs],
        "production_jobs": [_job_summary(j) for j in jobs],
    }


class RegenerateBriefBody(BaseModel):
    regenerate: bool = True


@router.post("/projects/{project_id}/briefs/regenerate", status_code=201)
async def regenerate_brief(
    project_id: str,
    body: RegenerateBriefBody,
    current_user: OperatorUser,
    db: DBSession,
):
    pid = _parse_uuid(project_id)
    project = await _require_owned_project(db, pid, current_user.organization_id)
    brief = await generate_brief_for_project(db, project=project, regenerate=body.regenerate)
    await db.commit()
    return _brief_summary(brief)


# ── Briefs ──────────────────────────────────────────────────────────────────


@router.get("/briefs/{brief_id}")
async def get_brief(
    brief_id: str,
    current_user: OperatorUser,
    db: DBSession,
):
    bid = _parse_uuid(brief_id)
    brief = (await db.execute(select(ProjectBrief).where(ProjectBrief.id == bid))).scalar_one_or_none()
    if brief is None or brief.org_id != current_user.organization_id:
        raise HTTPException(404, "Brief not found")
    return {
        **_brief_summary(brief),
        "project_id": str(brief.project_id),
        "summary": brief.summary,
        "goals": brief.goals,
        "audience": brief.audience,
        "tone_and_voice": brief.tone_and_voice,
        "deliverables": brief.deliverables_json,
        "assets": brief.assets_json,
        "source_intake_submission_id": str(brief.source_intake_submission_id)
        if brief.source_intake_submission_id
        else None,
    }


class LaunchProductionBody(BaseModel):
    job_type: str = "content_pack"
    title: str | None = None


@router.post("/briefs/{brief_id}/launch-production", status_code=201)
async def launch_production(
    brief_id: str,
    body: LaunchProductionBody,
    current_user: OperatorUser,
    db: DBSession,
):
    bid = _parse_uuid(brief_id)
    brief = (await db.execute(select(ProjectBrief).where(ProjectBrief.id == bid))).scalar_one_or_none()
    if brief is None or brief.org_id != current_user.organization_id:
        raise HTTPException(404, "Brief not found")
    job = await launch_production_for_brief(db, brief=brief, job_type=body.job_type, title=body.title)
    await db.commit()
    return _job_summary(job)


# ── Production jobs ─────────────────────────────────────────────────────────


@router.get("/production-jobs")
async def list_production_jobs(
    current_user: OperatorUser,
    db: DBSession,
    status: str | None = None,
    limit: int = 50,
):
    q = select(ProductionJob).where(
        ProductionJob.org_id == current_user.organization_id,
        ProductionJob.is_active.is_(True),
    )
    if status:
        q = q.where(ProductionJob.status == status)
    q = q.order_by(desc(ProductionJob.created_at)).limit(max(1, min(200, limit)))
    rows = (await db.execute(q)).scalars().all()
    return [_job_summary(j) for j in rows]


@router.get("/production-jobs/{job_id}")
async def get_production_job(
    job_id: str,
    current_user: OperatorUser,
    db: DBSession,
):
    jid = _parse_uuid(job_id)
    job = (await db.execute(select(ProductionJob).where(ProductionJob.id == jid))).scalar_one_or_none()
    if job is None or job.org_id != current_user.organization_id:
        raise HTTPException(404, "Production job not found")
    return {
        **_job_summary(job),
        "brief_id": str(job.brief_id),
        "project_id": str(job.project_id),
        "attempt_count": job.attempt_count,
        "retry_limit": job.retry_limit,
        "output_url": job.output_url,
        "output_payload": job.output_payload_json,
        "error_message": job.error_message,
        "metadata": job.metadata_json,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _project_summary(p: ClientProject) -> dict:
    return {
        "id": str(p.id),
        "status": p.status,
        "title": p.title,
        "package_slug": p.package_slug,
        "started_at": p.started_at.isoformat() if p.started_at else None,
        "due_at": p.due_at.isoformat() if p.due_at else None,
        "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        "created_at": p.created_at.isoformat(),
    }


def _brief_summary(b: ProjectBrief) -> dict:
    return {
        "id": str(b.id),
        "version": b.version,
        "status": b.status,
        "title": b.title,
        "generator": b.generator,
        "approved_at": b.approved_at.isoformat() if b.approved_at else None,
        "approved_by": b.approved_by,
        "created_at": b.created_at.isoformat(),
    }


def _job_summary(j: ProductionJob) -> dict:
    return {
        "id": str(j.id),
        "status": j.status,
        "job_type": j.job_type,
        "title": j.title,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        "attempt_count": j.attempt_count,
        "retry_limit": j.retry_limit,
        "output_url": j.output_url,
        "last_qa_report_id": str(j.last_qa_report_id) if j.last_qa_report_id else None,
        "created_at": j.created_at.isoformat(),
    }


def _parse_uuid(val: str) -> uuid.UUID:
    try:
        return uuid.UUID(val)
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid id")


async def _require_owned_project(db, project_id: uuid.UUID, org_id: uuid.UUID) -> ClientProject:
    project = (
        await db.execute(
            select(ClientProject).where(
                ClientProject.id == project_id,
                ClientProject.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(404, "Project not found")
    if project.org_id != org_id:
        raise HTTPException(403, "Project belongs to another organization")
    return project
