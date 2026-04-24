"""Pydantic schemas for MXP Audience State."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AudienceStateReportOut(BaseModel):
    id: str
    brand_id: str
    audience_segment_id: Optional[str] = None
    state_name: str
    state_score: float
    transition_probabilities_json: Optional[dict] = None
    best_next_action: str
    confidence_score: float
    explanation_json: Optional[dict] = None
    is_active: bool
    data_source: str = "synthetic_proxy"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
