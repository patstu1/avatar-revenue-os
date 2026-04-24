"""Pydantic schemas for MXP Reputation."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class ReputationReportOut(BaseModel):
    id: str
    brand_id: str
    scope_type: str
    scope_id: Optional[str] = None
    reputation_risk_score: float
    primary_risks_json: Optional[list[Any]] = None
    recommended_mitigation_json: Optional[list[Any]] = None
    expected_impact_if_unresolved: float
    confidence_score: float
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ReputationEventOut(BaseModel):
    id: str
    brand_id: str
    event_type: str
    severity: str
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    details_json: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
