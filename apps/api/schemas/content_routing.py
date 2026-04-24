"""Pydantic schemas for Content Routing APIs."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class RoutingDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    content_type: str
    quality_tier: str
    routed_provider: str
    platform: str
    is_promoted: bool
    estimated_cost: float
    actual_cost: float | None = None
    success: bool | None = None
    explanation: str | None = None


class CostReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    report_date: str
    total_cost: float
    total_decisions: int
    by_provider: dict | None = None
    by_tier: dict | None = None
    by_content_type: dict | None = None


class RouteTaskRequest(BaseModel):
    task_description: str
    platform: str
    content_type: str = "text"
    is_promoted: bool = False
    campaign_type: str = "organic"


class RouteTaskResponse(BaseModel):
    content_type: str
    quality_tier: str
    routed_provider: str
    estimated_cost: float
    platform: str
    explanation: str


class MonthlyProjectionOut(BaseModel):
    posts_per_month: int
    total_estimated_usd: float
    daily_average_usd: float
    cost_per_post_usd: float
    by_provider: dict
    platform_mix: dict


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    status: str = "completed"
