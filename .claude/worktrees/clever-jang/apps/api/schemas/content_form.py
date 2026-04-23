"""Content Form Selection schemas."""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ContentFormRecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: str
    recommended_content_form: str
    secondary_content_form: Optional[str] = None
    format_family: str
    short_or_long: str
    avatar_mode: str
    trust_level_required: str
    production_cost_band: str
    expected_upside: float
    expected_cost: float
    confidence: float
    urgency: float
    explanation: str
    truth_label: str
    blockers: Optional[list[Any]] = None


class ContentFormMixReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dimension: str
    dimension_value: str
    mix_allocation: dict[str, Any]
    total_expected_upside: float
    avg_confidence: float
    explanation: Optional[str] = None


class ContentFormBlockerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content_form: str
    blocker_type: str
    severity: str
    description: str
    operator_action: str
    resolved: bool


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    status: str = "completed"
