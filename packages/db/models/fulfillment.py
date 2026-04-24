"""Fulfillment backbone: client projects, project briefs, production jobs.

Introduced in Batch 3C. Bridges the Batch 3B intake completion into the
work that actually gets produced for the client:

    IntakeSubmission ──► ClientProject ──► ProjectBrief ──► ProductionJob

Schema is narrow. No speculative fields. Every table is org-scoped.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base

PROJECT_STATUSES = [
    "active",      # briefs being written / production running
    "on_hold",     # paused (awaiting info / operator decision)
    "completed",   # all deliveries sent
    "archived",
    "cancelled",
]

BRIEF_STATUSES = [
    "draft",       # generated but not approved
    "approved",    # operator approved; production can start
    "superseded",  # replaced by a newer version
]

PRODUCTION_JOB_STATUSES = [
    "queued",      # created, not yet picked up
    "running",     # worker actively producing
    "qa_pending",  # output available, awaiting QA
    "qa_passed",   # QA passed; ready for delivery
    "qa_failed",   # QA failed; may be retried
    "completed",   # delivered
    "cancelled",
    "failed",      # terminal failure after retry limit
]


# ── 1. ClientProject ─────────────────────────────────────────────────────────


class ClientProject(Base):
    """A unit of work owned by a paying client. Created from an
    IntakeSubmission. One client can have many projects over time.
    """
    __tablename__ = "client_projects"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True
    )

    # Source attribution — which intake + payment spawned this project
    intake_submission_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intake_submissions.id"), nullable=True, index=True
    )
    proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=True, index=True
    )
    payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    package_slug: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    status: Mapped[str] = mapped_column(
        String(30), default="active", nullable=False, index=True
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Batch 9: avenue attribution carried from the IntakeRequest.
    avenue_slug: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── 2. ProjectBrief ──────────────────────────────────────────────────────────


class ProjectBrief(Base):
    """A production brief for a client project. Generated from the intake
    responses. Versioned so the operator can re-generate without losing
    history.
    """
    __tablename__ = "project_briefs"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_project_briefs_project_version"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_projects.id"), nullable=False, index=True
    )

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="draft", nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    goals: Mapped[str] = mapped_column(Text, default="")
    audience: Mapped[str] = mapped_column(Text, default="")
    tone_and_voice: Mapped[str] = mapped_column(Text, default="")
    deliverables_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    assets_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    generator: Mapped[str] = mapped_column(String(50), default="template_v1")
    source_intake_submission_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intake_submissions.id"), nullable=True
    )

    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── 3. ProductionJob ─────────────────────────────────────────────────────────


class ProductionJob(Base):
    """A concrete production work order produced from a ProjectBrief.

    The actual media/output generation is delegated to the existing
    media_jobs/cinema_studio pipelines; this row is the canonical
    fulfillment-side status record so QA, retry and delivery can
    operate over a stable handle.
    """
    __tablename__ = "production_jobs"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_projects.id"), nullable=False, index=True
    )
    brief_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_briefs.id"), nullable=False, index=True
    )

    # What kind of output is this job producing (script/video/image/etc.)
    job_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    status: Mapped[str] = mapped_column(
        String(30), default="queued", nullable=False, index=True
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Retry / QA bookkeeping — used by Batch 3D QA loop
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_limit: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    last_qa_report_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Output — denormalised URL + payload hint for fast display
    output_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    output_payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Optional linkage to the existing media_jobs pipeline
    linked_media_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Batch 9: avenue attribution carried from the ClientProject.
    avenue_slug: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    # Batch 9: fulfillment-worker fields. When a worker picks up a pending
    # job, it stamps worker_id + picked_up_at + flips status to
    # in_progress. Used by the stuck-job detector to escalate.
    worker_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    picked_up_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
