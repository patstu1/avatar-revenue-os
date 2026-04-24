"""Pydantic schemas for MXP Contribution."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ContributionReportOut(BaseModel):
    id: str
    brand_id: str
    attribution_model: str
    scope_type: str
    scope_id: str | None = None
    estimated_contribution_value: float
    contribution_score: float
    confidence_score: float
    caveats_json: dict | None = None
    explanation_json: dict | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
