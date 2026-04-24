"""Pydantic schemas for Revenue Ceiling Phase B."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HighTicketOpportunityOut(BaseModel):
    id: str
    opportunity_key: str
    source_offer_id: str | None = None
    source_content_item_id: str | None = None
    eligibility_score: float = 0.0
    recommended_offer_path: dict[str, Any] | None = None
    recommended_cta: str | None = None
    expected_close_rate_proxy: float = 0.0
    expected_deal_value: float = 0.0
    expected_profit: float = 0.0
    confidence: float = 0.0
    explanation: str | None = None


class ProductOpportunityOut(BaseModel):
    id: str
    opportunity_key: str
    product_recommendation: str = ""
    product_type: str = ""
    target_audience: str | None = None
    price_range_min: float = 0.0
    price_range_max: float = 0.0
    expected_launch_value: float = 0.0
    expected_recurring_value: float | None = None
    build_complexity: str = "medium"
    confidence: float = 0.0
    explanation: str | None = None


class RevenueDensityReportOut(BaseModel):
    id: str
    content_item_id: str
    content_title: str | None = None
    revenue_per_content_item: float = 0.0
    revenue_per_1k_impressions: float = 0.0
    profit_per_1k_impressions: float = 0.0
    profit_per_audience_member: float = 0.0
    monetization_depth_score: float = 0.0
    repeat_monetization_score: float = 0.0
    ceiling_score: float = 0.0
    recommendation: str | None = None


class UpsellRecommendationOut(BaseModel):
    id: str
    opportunity_key: str
    anchor_offer_id: str | None = None
    anchor_content_item_id: str | None = None
    best_next_offer: dict[str, Any] | None = Field(default=None)
    best_timing: str = ""
    best_channel: str = ""
    expected_take_rate: float = 0.0
    expected_incremental_value: float = 0.0
    best_upsell_sequencing: dict[str, Any] | None = None
    confidence: float = 0.0
    explanation: str | None = None
