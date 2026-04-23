"""Pydantic schemas for Executive Intelligence."""
from __future__ import annotations
import uuid
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

class EIKPIOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; period: str; total_revenue: float; total_profit: float; total_spend: float; content_produced: int; content_published: int; avg_engagement_rate: float; active_accounts: int; active_campaigns: int

class EIForecastOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; forecast_type: str; forecast_period: str; predicted_value: float; confidence: float; explanation: Optional[str] = None

class EIUsageCostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; period: str; provider_key: Optional[str] = None; tasks_executed: int; cost_incurred: float

class EIUptimeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; provider_key: str; uptime_pct: float; reliability_grade: str; total_requests: int; failed_requests: int

class EIOversightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; mode: str; auto_approved_count: int; human_reviewed_count: int; override_count: int; ai_accuracy_estimate: float; recommendation: Optional[str] = None

class EIAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; alert_type: str; severity: str; title: str; detail: str; recommended_action: Optional[str] = None

class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0; status: str = "completed"
