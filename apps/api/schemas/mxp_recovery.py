"""Pydantic schemas for MXP Recovery."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RecoveryActionOut(BaseModel):
    id: str
    brand_id: str
    incident_id: str
    action_type: str
    action_mode: str
    executed: bool
    expected_effect_json: dict[str, Any] | None = None
    result_json: dict[str, Any] | None = None
    confidence_score: float
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RecoveryIncidentOut(BaseModel):
    id: str
    brand_id: str
    incident_type: str
    severity: str
    scope_type: str
    scope_id: str | None = None
    detected_at: datetime | None = None
    status: str
    explanation_json: dict[str, Any] | None = None
    is_active: bool
    escalation_state: str = "open"
    recommended_recovery_action: str | None = None
    automatic_action_taken: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    actions: list[RecoveryActionOut] = Field(default_factory=list)
    confidence: float | None = None
    expected_mitigation_effect: dict[str, Any] | None = None
