"""Pydantic schemas for MXP Deal Desk."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DealDeskRecommendationOut(BaseModel):
    id: str
    brand_id: str
    scope_type: str
    scope_id: Optional[str] = None
    deal_strategy: str
    pricing_stance: str
    packaging_recommendation_json: Optional[dict] = None
    expected_margin: float
    expected_close_probability: float
    confidence_score: float
    explanation_json: Optional[dict] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
