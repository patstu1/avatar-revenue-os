"""AI Buyer Trust Test — per-prospect Authority Score reports.

One row per submitted website-trust scan. Holds the composite + per-dimension
breakdown, evidence (detected/missing/why/fix per dimension), raw signals,
scanned-page transcript, recommended package, and the public-result envelope
returned to the form.

Lead handoff lives in ``lead_opportunities`` (existing table); this report
table is the deep per-prospect intelligence the operator reviews before
sending a snapshot or proposal. Stripe / payment metadata is unaffected —
``recommended_package_slug`` mirrors the universal slugs in
``apps/web/src/lib/proofhook-packages.ts`` so any operator-initiated
proposal flows through the existing package_slug → Stripe metadata chain.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class AuthorityScoreReport(Base):
    __tablename__ = "authority_score_reports"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True, index=True
    )
    lead_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lead_opportunities.id"), nullable=True, index=True
    )

    # Submitted prospect data
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    website_url: Mapped[str] = mapped_column(String(500), nullable=False)
    website_domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    competitor_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city_or_market: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Score outputs
    total_score: Mapped[int] = mapped_column(Integer, default=0)
    # ``authority_score`` is the public-facing label for total_score and is
    # written as a copy of total_score so future platform features (history,
    # trend, leaderboard) can evolve the semantic without a migration.
    authority_score: Mapped[int] = mapped_column(Integer, default=0)
    score_label: Mapped[str] = mapped_column(String(40), default="not_assessed")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    dimension_scores: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    technical_scores: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    evidence: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    raw_signals: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    scanned_pages: Mapped[list | None] = mapped_column(JSONB, default=list)
    top_gaps: Mapped[list | None] = mapped_column(JSONB, default=list)
    quick_wins: Mapped[list | None] = mapped_column(JSONB, default=list)
    recommended_package_slug: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_result: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    # Platform-ready fields — populated in patch 1 so the larger Decision-
    # Layer surfaces (history, monitoring, Authority Graph, snapshot
    # composer, proposal builder) can read from them without further
    # migrations. Each is JSON-shaped so the engine can evolve.
    authority_graph: Mapped[dict | None] = mapped_column(
        JSONB,
        default=dict,
        comment="Structured Authority Graph: entity, audience, offers, proof, comparisons, trust signals.",
    )
    buyer_questions: Mapped[list | None] = mapped_column(
        JSONB,
        default=list,
        comment="5–10 buyer questions the business should be prepared to answer publicly.",
    )
    recommended_pages: Mapped[list | None] = mapped_column(
        JSONB,
        default=list,
        comment="Pages ProofHook would build/refresh: [{slug, title, purpose, priority}].",
    )
    recommended_schema: Mapped[list | None] = mapped_column(
        JSONB,
        default=list,
        comment="JSON-LD blocks to add: [{type, target_url, why}].",
    )
    recommended_proof_assets: Mapped[list | None] = mapped_column(
        JSONB,
        default=list,
        comment="Proof assets to publish: [{kind, description, priority}].",
    )
    recommended_comparison_surfaces: Mapped[list | None] = mapped_column(
        JSONB,
        default=list,
        comment="Comparison surfaces to publish: [{kind, slug_pattern, purpose, priority}].",
    )
    monitoring_recommendation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="One-paragraph description of what monitoring would watch for this business.",
    )

    # Workflow
    report_status: Mapped[str] = mapped_column(
        String(30),
        default="queued",
        index=True,
        comment="queued | scanning | scored | proposal_created | qualified | archived | failed",
    )
    scan_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scan_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetch_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    formula_version: Mapped[str] = mapped_column(String(20), default="v1")
    report_version: Mapped[str] = mapped_column(
        String(20),
        default="v1",
        comment="Public-facing report shape version. Bumped when the public envelope schema changes.",
    )
    scan_version: Mapped[str] = mapped_column(
        String(20),
        default="v1",
        comment="Scanner capability version. Bumped when the extracted-signal shape changes.",
    )

    # Auditing / dedup
    request_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index("ix_authority_reports_org_created", "organization_id", "created_at"),
        Index("ix_authority_reports_domain_email", "website_domain", "contact_email"),
        Index("ix_authority_reports_status_created", "report_status", "created_at"),
    )
