"""Pydantic schemas for MXP Recovery."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class RecoveryActionOut(BaseModel):
    id: str
    brand_id: str
    incident_id: str
    action_type: str
    action_mode: str
    executed: bool
    expected_effect_json: Optional[dict[str, Any]] = None
    result_json: Optional[dict[str, Any]] = None
    confidence_score: float
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RecoveryIncidentOut(BaseModel):
    id: str
    brand_id: str
    incident_type: str
    severity: str
    scope_type: str
    scope_id: Optional[str] = None
    detected_at: Optional[datetime] = None
    status: str
    explanation_json: Optional[dict[str, Any]] = None
    is_active: bool
    escalation_state: str = "open"
    recommended_recovery_action: Optional[str] = None
    automatic_action_taken: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    actions: list[RecoveryActionOut] = Field(default_factory=list)
    confidence: Optional[float] = None
    expected_mitigation_effect: Optional[dict[str, Any]] = None
