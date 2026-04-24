"""Pydantic schemas for Revenue Ceiling Phase C."""

from __future__ import annotations

from typing import Any

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
    explanation: str | None = None


class SponsorInventoryItemOut(BaseModel):
    id: str
    brand_id: str
    content_item_id: str | None = None
    content_title: str | None = None
    sponsor_fit_score: float
    recommended_package_name: str | None = None
    estimated_package_price: float
    sponsor_category: str
    confidence: float
    explanation: str | None = None


class SponsorPackageRecommendationOut(BaseModel):
    id: str
    brand_id: str
    recommended_package: dict | None = None
    sponsor_fit_score: float
    estimated_package_price: float
    sponsor_category: str
    confidence: float
    explanation: str | None = None


class TrustConversionReportOut(BaseModel):
    id: str
    brand_id: str
    trust_deficit_score: float
    recommended_proof_blocks: Any | None = None
    missing_trust_elements: Any | None = None
    expected_uplift: float
    confidence: float
    explanation: str | None = None


class MonetizationMixReportOut(BaseModel):
    id: str
    brand_id: str
    current_revenue_mix: dict | None = None
    dependency_risk: float
    underused_monetization_paths: Any | None = None
    next_best_mix: dict | None = None
    expected_margin_uplift: float
    expected_ltv_uplift: float
    confidence: float
    explanation: str | None = None


class PaidPromotionCandidateOut(BaseModel):
    id: str
    brand_id: str
    content_item_id: str
    content_title: str | None = None
    organic_winner_evidence: dict | None = None
    is_eligible: bool
    gate_reason: str | None = None
    confidence: float
