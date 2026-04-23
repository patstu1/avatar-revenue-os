"""Pydantic schemas for MXP Contribution."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ContributionReportOut(BaseModel):
    id: str
    brand_id: str
    attribution_model: str
    scope_type: str
    scope_id: Optional[str] = None
    estimated_contribution_value: float
    contribution_score: float
    confidence_score: float
    caveats_json: Optional[dict] = None
    explanation_json: Optional[dict] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
