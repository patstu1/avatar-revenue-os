"""Pydantic schemas for Revenue Ceiling Phase C."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class RecurringRevenueModelOut(BaseModel):
    id: str
    brand_id: str
    recurring_potential_score: float
    best_recurring_offer_type: str
    audience_fit: float
    churn_risk_proxy: float
    expected_monthly_value: float
    expected_annual_value: float
    confidence: float
    explanation: Optional[str] = None


class SponsorInventoryItemOut(BaseModel):
    id: str
    brand_id: str
    content_item_id: Optional[str] = None
    content_title: Optional[str] = None
    sponsor_fit_score: float
    recommended_package_name: Optional[str] = None
    estimated_package_price: float
    sponsor_category: str
    confidence: float
    explanation: Optional[str] = None


class SponsorPackageRecommendationOut(BaseModel):
    id: str
    brand_id: str
    recommended_package: Optional[dict] = None
    sponsor_fit_score: float
    estimated_package_price: float
    sponsor_category: str
    confidence: float
    explanation: Optional[str] = None


class TrustConversionReportOut(BaseModel):
    id: str
    brand_id: str
    trust_deficit_score: float
    recommended_proof_blocks: Optional[Any] = None
    missing_trust_elements: Optional[Any] = None
    expected_uplift: float
    confidence: float
    explanation: Optional[str] = None


class MonetizationMixReportOut(BaseModel):
    id: str
    brand_id: str
    current_revenue_mix: Optional[dict] = None
    dependency_risk: float
    underused_monetization_paths: Optional[Any] = None
    next_best_mix: Optional[dict] = None
    expected_margin_uplift: float
    expected_ltv_uplift: float
    confidence: float
    explanation: Optional[str] = None


class PaidPromotionCandidateOut(BaseModel):
    id: str
    brand_id: str
    content_item_id: str
    content_title: Optional[str] = None
    organic_winner_evidence: Optional[dict] = None
    is_eligible: bool
    gate_reason: Optional[str] = None
    confidence: float
