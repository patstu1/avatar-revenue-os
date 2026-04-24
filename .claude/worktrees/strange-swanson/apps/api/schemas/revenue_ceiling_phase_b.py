"""Pydantic schemas for Revenue Ceiling Phase B."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class HighTicketOpportunityOut(BaseModel):
    id: str
    opportunity_key: str
    source_offer_id: Optional[str] = None
    source_content_item_id: Optional[str] = None
    eligibility_score: float = 0.0
    recommended_offer_path: Optional[dict[str, Any]] = None
    recommended_cta: Optional[str] = None
    expected_close_rate_proxy: float = 0.0
    expected_deal_value: float = 0.0
    expected_profit: float = 0.0
    confidence: float = 0.0
    explanation: Optional[str] = None


class ProductOpportunityOut(BaseModel):
    id: str
    opportunity_key: str
    product_recommendation: str = ""
    product_type: str = ""
    target_audience: Optional[str] = None
    price_range_min: float = 0.0
    price_range_max: float = 0.0
    expected_launch_value: float = 0.0
    expected_recurring_value: Optional[float] = None
    build_complexity: str = "medium"
    confidence: float = 0.0
    explanation: Optional[str] = None


class RevenueDensityReportOut(BaseModel):
    id: str
    content_item_id: str
    content_title: Optional[str] = None
    revenue_per_content_item: float = 0.0
    revenue_per_1k_impressions: float = 0.0
    profit_per_1k_impressions: float = 0.0
    profit_per_audience_member: float = 0.0
    monetization_depth_score: float = 0.0
    repeat_monetization_score: float = 0.0
    ceiling_score: float = 0.0
    recommendation: Optional[str] = None


class UpsellRecommendationOut(BaseModel):
    id: str
    opportunity_key: str
    anchor_offer_id: Optional[str] = None
    anchor_content_item_id: Optional[str] = None
    best_next_offer: Optional[dict[str, Any]] = Field(default=None)
    best_timing: str = ""
    best_channel: str = ""
    expected_take_rate: float = 0.0
    expected_incremental_value: float = 0.0
    best_upsell_sequencing: Optional[dict[str, Any]] = None
    confidence: float = 0.0
    explanation: Optional[str] = None
