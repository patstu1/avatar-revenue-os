"""Pydantic schemas for MXP Capacity."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CapacityReportOut(BaseModel):
    id: str
    brand_id: str
    capacity_type: str
    current_capacity: float
    used_capacity: float
    constrained_scope_json: dict | None = None
    recommended_volume: float
    recommended_throttle: float | None = None
    expected_profit_impact: float
    confidence_score: float
    explanation_json: dict | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class QueueAllocationDecisionOut(BaseModel):
    id: str
    brand_id: str
    queue_name: str
    priority_score: float
    allocated_capacity: float
    deferred_capacity: float
    reason_json: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
