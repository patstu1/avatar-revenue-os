"""AI Search Authority — public diagnostic reports for ProofHook.

A report is created when a visitor submits the public AI Buyer Trust Test
diagnostic. The Report is the entity that:

  - persists the submitter's answers + computed score/tier/gaps
  - links to the LeadOpportunity created from the same submission
  - tracks status transitions (submitted → snapshot_requested → proposal_sent)
  - links to the Proposal created downstream by the operator

V1 is answer-based — no real public website scanning. The diagnostic is
deterministic over the submitted answers and is labelled accordingly to
the buyer.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class AISearchAuthorityReport(Base):
    """Persistent record of a public AI Buyer Trust Test submission.

    Public submissions arrive without auth. ``organization_id`` and
    ``brand_id`` are filled in from the canonical ProofHook brand so the
    LeadOpportunity created alongside this report can attach to a brand
    (LeadOpportunity.brand_id is NOT NULL upstream).
    """

    __tablename__ = "ai_search_authority_reports"

    # Org/brand context. Both nullable so the row can land even if the
    # canonical ProofHook brand has not yet been seeded.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True, index=True
    )

    # Submitter identity (collected on the public form)
    submitter_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    submitter_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    submitter_company: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    submitter_url: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    submitter_role: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    submitter_revenue_band: Mapped[str] = mapped_column(String(60), default="", nullable=False)

    # Optional context fields the public site already passes to Stripe
    # metadata. Persisted so attribution stays consistent end-to-end.
    vertical: Mapped[str] = mapped_column(String(60), default="", nullable=False, index=True)
    buyer_type: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    industry_context: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    # Diagnostic raw input + computed output
    answers_json: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(20), default="cold", nullable=False, index=True)
    gaps_json: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)
    quick_win: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # Recommendation — must be one of the approved ProofHook package slugs.
    # Enforcement lives in the service layer; the column is a free string
    # for forward compatibility with future approved slugs.
    recommended_package_slug: Mapped[str] = mapped_column(
        String(100), default="", nullable=False, index=True
    )

    # State machine
    # submitted → snapshot_requested → proposal_sent → won | lost
    status: Mapped[str] = mapped_column(
        String(40), default="submitted", nullable=False, index=True
    )
    snapshot_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    proposal_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Cross-references to existing Revenue OS systems
    lead_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lead_opportunities.id"), nullable=True, index=True
    )
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=True, index=True
    )

    # Provenance
    source: Mapped[str] = mapped_column(String(60), default="public", nullable=False)
    submission_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_aisa_reports_status_created", "status", "created_at"),
        Index("ix_aisa_reports_email_created", "submitter_email", "created_at"),
    )
