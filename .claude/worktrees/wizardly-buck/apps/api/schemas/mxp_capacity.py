"""Pydantic schemas for MXP Capacity."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CapacityReportOut(BaseModel):
    id: str
    brand_id: str
    capacity_type: str
    current_capacity: float
    used_capacity: float
    constrained_scope_json: Optional[dict] = None
    recommended_volume: float
    recommended_throttle: Optional[float] = None
    expected_profit_impact: float
    confidence_score: float
    explanation_json: Optional[dict] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class QueueAllocationDecisionOut(BaseModel):
    id: str
    brand_id: str
    queue_name: str
    priority_score: float
    allocated_capacity: float
    deferred_capacity: float
    reason_json: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
