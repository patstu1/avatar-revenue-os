"""Pydantic schemas for MXP Deal Desk."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DealDeskRecommendationOut(BaseModel):
    id: str
    brand_id: str
    scope_type: str
    scope_id: str | None = None
    deal_strategy: str
    pricing_stance: str
    packaging_recommendation_json: dict | None = None
    expected_margin: float
    expected_close_probability: float
    confidence_score: float
    explanation_json: dict | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
