"""Pydantic schemas for MXP Reputation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ReputationReportOut(BaseModel):
    id: str
    brand_id: str
    scope_type: str
    scope_id: str | None = None
    reputation_risk_score: float
    primary_risks_json: list[Any] | None = None
    recommended_mitigation_json: list[Any] | None = None
    expected_impact_if_unresolved: float
    confidence_score: float
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReputationEventOut(BaseModel):
    id: str
    brand_id: str
    event_type: str
    severity: str
    scope_type: str | None = None
    scope_id: str | None = None
    details_json: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
