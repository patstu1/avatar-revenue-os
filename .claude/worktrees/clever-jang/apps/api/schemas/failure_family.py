"""Pydantic schemas for Failure-Family Suppression."""
from __future__ import annotations
import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict


class FFReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    family_type: str
    family_key: str
    failure_count: int
    avg_fail_score: float
    recommended_alternative: Optional[str] = None
    explanation: Optional[str] = None


class SuppressionRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    family_type: str
    family_key: str
    suppression_mode: str
    retest_after_days: int
    reason: Optional[str] = None
    is_active: bool


class SuppressionEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    blocked_target: str
    blocked_context: str
    explanation: Optional[str] = None


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    status: str = "completed"
