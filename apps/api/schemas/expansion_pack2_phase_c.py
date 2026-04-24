"""Pydantic schemas for Expansion Pack 2 Phase C."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReferralProgramRecommendationOut(BaseModel):
    id: str
    brand_id: str
    customer_segment: str
    recommendation_type: str
    referral_bonus: float
    referred_bonus: float
    estimated_conversion_rate: float
    estimated_revenue_impact: float
    confidence: float
    explanation: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CompetitiveGapReportOut(BaseModel):
    id: str
    brand_id: str
    offer_id: str | None = None
    competitor_name: str
    gap_type: str
    gap_description: str | None = None
    severity: str
    estimated_impact: float
    confidence: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SponsorTargetOut(BaseModel):
    id: str
    brand_id: str
    target_company_name: str
    industry: str | None = None
    contact_info: dict | None = None
    estimated_deal_value: float
    fit_score: float
    confidence: float
    explanation: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SponsorOutreachSequenceOut(BaseModel):
    id: str
    sponsor_target_id: str
    sequence_name: str
    steps: list[dict]
    estimated_response_rate: float
    expected_value: float
    confidence: float
    explanation: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProfitGuardrailReportOut(BaseModel):
    id: str
    brand_id: str
    metric_name: str
    current_value: float
    threshold_value: float
    status: str
    action_recommended: str | None = None
    estimated_impact: float
    confidence: float
    is_active: bool
    created_at: datetime
    updated_at: datetime
