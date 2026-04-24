"""Pydantic schemas for Portfolio Capital Allocator."""
from __future__ import annotations
import uuid
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class AllocationReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    total_budget: float
    allocated_budget: float
    experiment_reserve: float
    hero_spend: float
    bulk_spend: float
    target_count: int
    starved_count: int


class AllocationTargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    target_type: str
    target_key: str
    expected_return: float
    expected_cost: float
    confidence: float
    account_health: float
    fatigue_score: float
    pattern_win_score: float
    provider_tier: str


class AllocationDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    allocated_budget: float
    allocated_volume: int
    provider_tier: str
    allocation_pct: float
    starved: bool
    explanation: Optional[str] = None


class AllocationRebalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    rebalance_reason: str
    targets_starved: int
    targets_boosted: int


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    status: str = "completed"
