"""Pydantic schemas for Expansion Pack 2 Phase A."""

from __future__ import annotations

from pydantic import BaseModel


class LeadOpportunityOut(BaseModel):
    id: str
    brand_id: str
    lead_source: str
    message_text: str | None = None
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
    explanation: str | None = None


class CloserActionOut(BaseModel):
    id: str
    brand_id: str
    lead_opportunity_id: str | None = None
    action_type: str
    priority: int
    channel: str
    subject_or_opener: str
    timing: str
    rationale: str | None = None
    expected_outcome: str | None = None
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
    signal_summary: dict | None = None
    confidence: float
    explanation: str | None = None


class OwnedOfferRecommendationOut(BaseModel):
    id: str
    brand_id: str
    opportunity_key: str
    signal_type: str
    detected_signal: str | None = None
    recommended_offer_type: str
    offer_name_suggestion: str
    price_point_min: float
    price_point_max: float
    estimated_demand_score: float
    estimated_first_month_revenue: float
    audience_fit: str | None = None
    confidence: float
    explanation: str | None = None
    build_priority: str
