"""Pydantic schemas for MXP Offer Lifecycle."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class OfferLifecycleReportOut(BaseModel):
    id: str
    brand_id: str
    offer_id: str
    lifecycle_state: str
    health_score: float
    dependency_risk_score: float
    decay_score: float
    recommended_next_action: str | None = None
    expected_impact_json: dict | None = None
    confidence_score: float
    explanation_json: dict | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OfferLifecycleEventOut(BaseModel):
    id: str
    brand_id: str
    offer_id: str
    event_type: str
    from_state: str | None = None
    to_state: str | None = None
    reason_json: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
