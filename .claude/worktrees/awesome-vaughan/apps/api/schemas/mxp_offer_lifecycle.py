"""Pydantic schemas for MXP Offer Lifecycle."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OfferLifecycleReportOut(BaseModel):
    id: str
    brand_id: str
    offer_id: str
    lifecycle_state: str
    health_score: float
    dependency_risk_score: float
    decay_score: float
    recommended_next_action: Optional[str] = None
    expected_impact_json: Optional[dict] = None
    confidence_score: float
    explanation_json: Optional[dict] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OfferLifecycleEventOut(BaseModel):
    id: str
    brand_id: str
    offer_id: str
    event_type: str
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    reason_json: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
