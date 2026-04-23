"""Pydantic schemas for Opportunity-Cost Ranking."""
from __future__ import annotations
import uuid
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class OCReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    total_actions: int
    top_action_type: Optional[str] = None
    total_opportunity_cost: float
    safe_to_wait_count: int
    summary: Optional[str] = None


class RankedActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    action_type: str
    action_key: str
    expected_upside: float
    cost_of_delay: float
    urgency: float
    confidence: float
    composite_rank: float
    rank_position: int
    safe_to_wait: bool
    explanation: Optional[str] = None


class CostOfDelayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    action_type: str
    action_key: str
    daily_cost: float
    weekly_cost: float
    time_sensitivity: str


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    status: str = "completed"
