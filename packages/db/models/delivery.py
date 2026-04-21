"""QA reviews + deliveries (Batch 3D).

Introduced to close the production → QA → retry → delivery → followup
loop. The existing ``QAReport`` table is content-layer scoped (keyed by
``content_item_id``); this module adds a narrow production-layer
analogue (``ProductionQAReview``) so ProductionJob-scoped QA + retry
can be reasoned over without touching the legacy schema.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


QA_RESULTS = ["passed", "failed", "needs_review"]
DELIVERY_STATUSES = ["pending", "sent", "failed", "acknowledged"]


# ── 1. ProductionQAReview ────────────────────────────────────────────────────


class ProductionQAReview(Base):
    """A QA review of a specific attempt of a ProductionJob.

    One-per-attempt. Holds the pass/fail verdict plus a compact score
    summary and reviewer attribution. Retry bookkeeping lives on the
    ProductionJob row (attempt_count, retry_limit, last_qa_report_id).
    """
    __tablename__ = "production_qa_reviews"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    production_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("production_jobs.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_projects.id"), nullable=False, index=True
    )

    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    result: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )
    composite_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    scores_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    issues_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    reviewer_type: Mapped[str] = mapped_column(String(30), default="auto", nullable=False)
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── 2. Delivery ──────────────────────────────────────────────────────────────


class Delivery(Base):
    """A delivery of completed work to a paying client.

    One-per-dispatch. Holds the deliverable URL (or payload pointer), the
    send channel, status, and the scheduled follow-up date. Email body
    generation is delegated to the email_templates / SMTP client layer;
    this row is the canonical record that a delivery was produced.
    """
    __tablename__ = "deliveries"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_projects.id"), nullable=False, index=True
    )
    production_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("production_jobs.id"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), default="email", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)

    deliverable_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    recipient_email: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    subject: Mapped[str] = mapped_column(String(1000), default="")
    message: Mapped[str] = mapped_column(Text, default="")

    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    followup_scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Batch 9: set by the follow-up sender beat task when the scheduled
    # message is actually delivered. Selected by
    # `followup_sent_at IS NULL AND followup_scheduled_at <= now()`.
    followup_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Batch 9: avenue attribution carried from the ProductionJob.
    avenue_slug: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
