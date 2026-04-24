"""Pydantic schemas for Expansion Pack 2 Phase A."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class LeadOpportunityOut(BaseModel):
    id: str
    brand_id: str
    lead_source: str
    message_text: Optional[str] = None
    urgency_score: float
    budget_proxy_score: float
    sophistication_score: float
    offer_fit_score: float
    trust_readiness_score: float
    composite_score: float
    qualification_tier: str
    recommended_action: str
    expected_value: float
    likelihood_to_close: float
    channel_preference: str
    confidence: float
    explanation: Optional[str] = None


class CloserActionOut(BaseModel):
    id: str
    brand_id: str
    lead_opportunity_id: Optional[str] = None
    action_type: str
    priority: int
    channel: str
    subject_or_opener: str
    timing: str
    rationale: Optional[str] = None
    expected_outcome: Optional[str] = None
    is_completed: bool


class LeadQualificationReportOut(BaseModel):
    id: str
    brand_id: str
    total_leads_scored: int
    hot_leads: int
    warm_leads: int
    cold_leads: int
    avg_composite_score: float
    avg_expected_value: float
    top_channel: str
    top_recommended_action: str
    signal_summary: Optional[dict] = None
    confidence: float
    explanation: Optional[str] = None


class OwnedOfferRecommendationOut(BaseModel):
    id: str
    brand_id: str
    opportunity_key: str
    signal_type: str
    detected_signal: Optional[str] = None
    recommended_offer_type: str
    offer_name_suggestion: str
    price_point_min: float
    price_point_max: float
    estimated_demand_score: float
    estimated_first_month_revenue: float
    audience_fit: Optional[str] = None
    confidence: float
    explanation: Optional[str] = None
    build_priority: str
