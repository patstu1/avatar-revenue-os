"""Pydantic schemas for Expansion Pack 2 Phase B."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel


class PricingRecommendationOut(BaseModel):
    id: str
    brand_id: str
    offer_id: str
    recommendation_type: str
    current_price: float
    recommended_price: float
    price_elasticity: float
    estimated_revenue_impact: float
    confidence: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BundleRecommendationOut(BaseModel):
    id: str
    brand_id: str
    bundle_name: str
    offer_ids: list[str]
    recommended_bundle_price: float
    estimated_upsell_rate: float
    estimated_revenue_impact: float
    confidence: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RetentionRecommendationOut(BaseModel):
    id: str
    brand_id: str
    customer_segment: str
    recommendation_type: str
    action_details: Optional[dict] = None
    estimated_retention_lift: float
    confidence: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ReactivationCampaignOut(BaseModel):
    id: str
    brand_id: str
    campaign_name: str
    target_segment: str
    campaign_type: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    estimated_reactivation_rate: float
    estimated_revenue_impact: float
    confidence: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
