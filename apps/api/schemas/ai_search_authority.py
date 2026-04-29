"""Pydantic schemas for the AI Search Authority public diagnostic + operator endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ScoreSubmitRequest(BaseModel):
    """Public submission of the AI Buyer Trust Test diagnostic.

    Free-text and answer fields. Identity fields are required so the
    LeadOpportunity created downstream can be followed up. ``answers`` is
    a free-shape dict — the service computes the score from the keys it
    recognises and stores the rest verbatim.
    """

    submitter_email: EmailStr
    submitter_name: str = Field(default="", max_length=255)
    submitter_company: str = Field(default="", max_length=255)
    submitter_url: str = Field(default="", max_length=1024)
    submitter_role: str = Field(default="", max_length=100)
    submitter_revenue_band: str = Field(default="", max_length=60)
    vertical: str = Field(default="", max_length=60)
    buyer_type: str = Field(default="", max_length=60)
    industry_context: str = Field(default="", max_length=255)
    answers: dict[str, Any] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=2000)


class GapItem(BaseModel):
    key: str
    label: str
    weight: float
    severity: str  # "high" | "medium" | "low"


class ScoreSubmitResponse(BaseModel):
    report_id: uuid.UUID
    score: float
    tier: str
    gaps: list[GapItem]
    quick_win: str
    recommended_package_slug: str
    recommended_package_path: str
    diagnostic_kind: str = "answer_based"
    status: str


class SnapshotReviewResponse(BaseModel):
    report_id: uuid.UUID
    status: str
    snapshot_requested_at: datetime
    deduped: bool


class ReportListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submitter_email: str
    submitter_company: str
    score: float
    tier: str
    recommended_package_slug: str
    status: str
    vertical: str
    created_at: datetime


class ReportDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    submitter_email: str
    submitter_name: str
    submitter_company: str
    submitter_url: str
    submitter_role: str
    submitter_revenue_band: str
    vertical: str
    buyer_type: str
    industry_context: str
    answers_json: dict[str, Any] | None = None
    score: float
    tier: str
    gaps_json: list[dict[str, Any]] | None = None
    quick_win: str
    recommended_package_slug: str
    status: str
    snapshot_requested_at: datetime | None = None
    proposal_created_at: datetime | None = None
    closed_at: datetime | None = None
    lead_opportunity_id: uuid.UUID | None = None
    proposal_id: uuid.UUID | None = None
    source: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class CreateProposalRequest(BaseModel):
    """Operator override of which package to propose.

    If ``package_slug`` is omitted, the report's ``recommended_package_slug``
    is used. Both must be one of the approved ProofHook slugs.
    """

    package_slug: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, max_length=500)
    summary: str | None = Field(default=None, max_length=4000)
    unit_amount_cents_override: int | None = Field(default=None, ge=0)
    currency: str = Field(default="usd", max_length=10)
    notes: str | None = Field(default=None, max_length=4000)


class CreateProposalResponse(BaseModel):
    report_id: uuid.UUID
    proposal_id: uuid.UUID
    package_slug: str
    total_amount_cents: int
    currency: str
    status: str
