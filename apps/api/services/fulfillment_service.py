"""Fulfillment orchestration (Batch 3C).

Bridges intake.completed → ClientProject → ProjectBrief → ProductionJob,
emitting the canonical events at every transition.

Called from:
  - ``client_activation.submit_intake`` (auto, on completed submission)
  - GET/POST project & brief routes (manual)
  - QA/delivery workers (Batch 3D, for retry/finalize transitions)
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.db.models.clients import (
    Client,
    ClientOnboardingEvent,
    IntakeRequest,
    IntakeSubmission,
)
from packages.db.models.fulfillment import (
    ClientProject,
    ProductionJob,
    ProjectBrief,
)

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════════════
#  ClientProject
# ═══════════════════════════════════════════════════════════════════════════


async def create_project_from_intake(
    db: AsyncSession,
    *,
    intake_submission: IntakeSubmission,
) -> tuple[ClientProject, bool]:
    """Create a ClientProject for a completed IntakeSubmission (idempotent
    on intake_submission_id).

    Returns ``(project, is_new)``. On duplicate calls returns the existing
    project unchanged.

    Emits ``project.created`` only on first insert.
    """
    existing = (
        await db.execute(select(ClientProject).where(ClientProject.intake_submission_id == intake_submission.id))
    ).scalar_one_or_none()
    if existing is not None:
        return (existing, False)

    intake_request = (
        await db.execute(select(IntakeRequest).where(IntakeRequest.id == intake_submission.intake_request_id))
    ).scalar_one_or_none()
    client = (await db.execute(select(Client).where(Client.id == intake_submission.client_id))).scalar_one()

    title = f"Project for {client.display_name or client.primary_email}"
    description = ""
    responses = intake_submission.responses_json or {}
    if isinstance(responses, dict):
        goals = responses.get("goals") or responses.get("target_audience")
        if goals:
            description = str(goals)[:2000]

    package_slug = None
    if intake_request and intake_request.proposal_id:
        from packages.db.models.proposals import Proposal

        proposal = (
            await db.execute(select(Proposal).where(Proposal.id == intake_request.proposal_id))
        ).scalar_one_or_none()
        if proposal is not None:
            package_slug = proposal.package_slug
            title = proposal.title or title

    now = datetime.now(timezone.utc)
    # Batch 9: carry avenue_slug through. Intake request is the most
    # recently-set carrier; fall back to proposal if intake didn't have it.
    avenue_slug = None
    if intake_request is not None:
        avenue_slug = intake_request.avenue_slug
    if avenue_slug is None and intake_request and intake_request.proposal_id:
        from packages.db.models.proposals import Proposal

        proposal_row = (
            await db.execute(select(Proposal).where(Proposal.id == intake_request.proposal_id))
        ).scalar_one_or_none()
        if proposal_row is not None:
            avenue_slug = proposal_row.avenue_slug

    project = ClientProject(
        org_id=intake_submission.org_id,
        client_id=intake_submission.client_id,
        intake_submission_id=intake_submission.id,
        proposal_id=intake_request.proposal_id if intake_request else None,
        payment_id=intake_request.payment_id if intake_request else None,
        title=title[:500],
        description=description,
        package_slug=package_slug,
        avenue_slug=avenue_slug,
        status="active",
        started_at=now,
        metadata_json={"source": "intake_submission", "responses": responses},
    )
    db.add(project)
    await db.flush()

    db.add(
        ClientOnboardingEvent(
            client_id=intake_submission.client_id,
            org_id=intake_submission.org_id,
            event_type="project.created",
            intake_request_id=intake_submission.intake_request_id,
            intake_submission_id=intake_submission.id,
            details_json={"project_id": str(project.id), "title": project.title},
            actor_type="system",
            actor_id="fulfillment_service",
        )
    )
    await db.flush()

    await emit_event(
        db,
        domain="fulfillment",
        event_type="project.created",
        summary=f"Project created for client {client.display_name}: {project.title[:80]}",
        org_id=project.org_id,
        entity_type="client_project",
        entity_id=project.id,
        new_state="active",
        actor_type="system",
        actor_id="fulfillment_service",
        details={
            "project_id": str(project.id),
            "client_id": str(project.client_id),
            "intake_submission_id": str(intake_submission.id),
            "proposal_id": str(project.proposal_id) if project.proposal_id else None,
            "package_slug": package_slug,
        },
    )
    logger.info(
        "project.created",
        project_id=str(project.id),
        client_id=str(project.client_id),
    )
    return (project, True)


# ═══════════════════════════════════════════════════════════════════════════
#  ProjectBrief
# ═══════════════════════════════════════════════════════════════════════════


async def generate_brief_for_project(
    db: AsyncSession,
    *,
    project: ClientProject,
    regenerate: bool = False,
) -> ProjectBrief:
    """Generate the next ProjectBrief for a project from its intake
    responses.

    Idempotent — when a brief already exists for the project, returns it
    unchanged. Set ``regenerate=True`` to write a new version (the prior
    version is marked ``status=superseded``).

    Emits ``brief.created`` on new insert only.
    """
    if not regenerate:
        existing = (
            await db.execute(
                select(ProjectBrief)
                .where(
                    ProjectBrief.project_id == project.id,
                    ProjectBrief.is_active.is_(True),
                )
                .order_by(ProjectBrief.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    if regenerate:
        current_version = (
            await db.execute(
                select(func.coalesce(func.max(ProjectBrief.version), 0)).where(ProjectBrief.project_id == project.id)
            )
        ).scalar() or 0
        # Mark all prior active versions superseded
        prior = (
            (
                await db.execute(
                    select(ProjectBrief).where(
                        ProjectBrief.project_id == project.id,
                        ProjectBrief.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        for p in prior:
            p.status = "superseded"
        await db.flush()
        next_version = current_version + 1
    else:
        next_version = 1

    # Build from intake responses
    responses = {}
    intake_sub = None
    if project.intake_submission_id is not None:
        intake_sub = (
            await db.execute(select(IntakeSubmission).where(IntakeSubmission.id == project.intake_submission_id))
        ).scalar_one_or_none()
        if intake_sub is not None:
            responses = intake_sub.responses_json or {}

    def _s(key: str, default: str = "") -> str:
        val = responses.get(key) if isinstance(responses, dict) else None
        return str(val) if val else default

    brief = ProjectBrief(
        org_id=project.org_id,
        project_id=project.id,
        version=next_version,
        status="draft",
        title=f"Brief v{next_version} — {project.title[:400]}",
        summary=project.description or _s("goals"),
        goals=_s("goals"),
        audience=_s("target_audience"),
        tone_and_voice=_s("brand_voice"),
        deliverables_json={"package_slug": project.package_slug} if project.package_slug else None,
        assets_json=({"assets_url": _s("assets_url")} if _s("assets_url") else None),
        generator="template_v1",
        source_intake_submission_id=project.intake_submission_id,
    )
    db.add(brief)
    await db.flush()

    await emit_event(
        db,
        domain="fulfillment",
        event_type="brief.created",
        summary=f"Brief v{brief.version} generated for project {project.title[:60]}",
        org_id=project.org_id,
        entity_type="project_brief",
        entity_id=brief.id,
        new_state="draft",
        actor_type="system",
        actor_id="fulfillment_service",
        details={
            "brief_id": str(brief.id),
            "project_id": str(project.id),
            "version": brief.version,
            "generator": brief.generator,
        },
    )
    logger.info(
        "brief.created",
        brief_id=str(brief.id),
        project_id=str(project.id),
        version=brief.version,
    )
    return brief


async def approve_brief(
    db: AsyncSession,
    *,
    brief: ProjectBrief,
    approver_email: str,
    approver_id: str,
) -> ProjectBrief:
    """Approve a brief so production can start. Idempotent."""
    if brief.status == "approved":
        return brief
    if brief.status == "superseded":
        raise ValueError("Cannot approve a superseded brief")

    now = datetime.now(timezone.utc)
    brief.status = "approved"
    brief.approved_by = approver_email[:255]
    brief.approved_at = now
    await db.flush()
    return brief


# ═══════════════════════════════════════════════════════════════════════════
#  ProductionJob
# ═══════════════════════════════════════════════════════════════════════════


async def launch_production_for_brief(
    db: AsyncSession,
    *,
    brief: ProjectBrief,
    job_type: str = "content_pack",
    title: str | None = None,
    metadata: dict | None = None,
) -> ProductionJob:
    """Create a ProductionJob for an approved brief.

    Auto-approves the brief if still in ``draft`` state (system flow:
    intake.completed cascades straight through production start for
    packaged offerings; operator approval gate is deferred to Batch 4).

    Idempotent — returns existing active production job if one already
    exists for this brief.

    Emits ``production.started`` on first insert, transitions status →
    running.
    """
    existing = (
        await db.execute(
            select(ProductionJob).where(
                ProductionJob.brief_id == brief.id,
                ProductionJob.is_active.is_(True),
                ProductionJob.status.in_(("queued", "running", "qa_pending", "qa_passed")),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    if brief.status == "draft":
        brief.status = "approved"
        brief.approved_at = datetime.now(timezone.utc)
        brief.approved_by = brief.approved_by or "system:auto_approve"
        await db.flush()

    # Batch 9: carry avenue_slug from the project.
    project_row = (
        await db.execute(select(ClientProject).where(ClientProject.id == brief.project_id))
    ).scalar_one_or_none()
    avenue_slug = project_row.avenue_slug if project_row is not None else None

    now = datetime.now(timezone.utc)
    job = ProductionJob(
        org_id=brief.org_id,
        project_id=brief.project_id,
        brief_id=brief.id,
        job_type=job_type,
        title=(title or f"{job_type}: {brief.title[:400]}")[:500],
        status="queued",
        started_at=now,
        attempt_count=0,
        metadata_json=metadata,
        avenue_slug=avenue_slug,
    )
    db.add(job)
    await db.flush()

    await emit_event(
        db,
        domain="fulfillment",
        event_type="production.queued",
        summary=f"Production queued: {job.title[:80]}",
        org_id=job.org_id,
        entity_type="production_job",
        entity_id=job.id,
        new_state="queued",
        actor_type="system",
        actor_id="fulfillment_service",
        details={
            "production_job_id": str(job.id),
            "brief_id": str(brief.id),
            "project_id": str(brief.project_id),
            "job_type": job_type,
            "avenue_slug": avenue_slug,
        },
    )
    logger.info(
        "production.queued",
        production_job_id=str(job.id),
        brief_id=str(brief.id),
        avenue_slug=avenue_slug,
    )
    try:
        from apps.api.services.stage_controller import mark_stage

        await mark_stage(
            db,
            org_id=job.org_id,
            entity_type="production_job",
            entity_id=job.id,
            stage="queued",
        )
    except Exception as stage_exc:
        logger.warning("stage_controller.mark_failed", entity="production_job", error=str(stage_exc)[:150])
    return job


# ═══════════════════════════════════════════════════════════════════════════
#  Cascade entry point (called from intake completion)
# ═══════════════════════════════════════════════════════════════════════════


async def cascade_intake_to_production(
    db: AsyncSession,
    *,
    intake_submission: IntakeSubmission,
) -> dict:
    """End-to-end intake.completed → project → brief → production cascade.

    Called from ``client_activation.submit_intake`` when ``is_complete``
    flips to True. Every stage is idempotent so retrying this cascade
    across webhook redeliveries / partial failures is safe.
    """
    project, project_is_new = await create_project_from_intake(db, intake_submission=intake_submission)
    brief = await generate_brief_for_project(db, project=project)
    production_job = await launch_production_for_brief(db, brief=brief)

    return {
        "project_id": str(project.id),
        "project_is_new": project_is_new,
        "brief_id": str(brief.id),
        "brief_version": brief.version,
        "production_job_id": str(production_job.id),
        "production_status": production_job.status,
    }
