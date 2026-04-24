"""Pydantic models for revenue ceiling APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MonetizationRecRow(BaseModel):
    id: str
    content_item_id: str | None = None
    recommendation_type: str
    title: str
    description: str | None = None
    expected_revenue_uplift: float = 0.0
    expected_cost: float = 0.0
    confidence: float = 0.0
    evidence: dict[str, Any] | None = None
    is_actioned: bool = False


class RevenueIntelDashboardResponse(BaseModel):
    brand_id: str
    offer_stacks: list[MonetizationRecRow] = Field(default_factory=list)
    funnel_paths: list[MonetizationRecRow] = Field(default_factory=list)
    owned_audience: list[MonetizationRecRow] = Field(default_factory=list)
    productization: list[MonetizationRecRow] = Field(default_factory=list)
    density_improvements: list[MonetizationRecRow] = Field(default_factory=list)
