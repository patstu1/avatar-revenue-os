"""Pydantic models for Phase 6 growth intelligence APIs."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AudienceSegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    segment_criteria: dict[str, Any] | None = None
    estimated_size: int = 0
    revenue_contribution: float = 0.0
    conversion_rate: float = 0.0
    avg_ltv: float = 0.0
    platforms: Any | None = None
    is_active: bool = True


class LtvModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    segment_name: str
    model_type: str = "rules_based"
    parameters: dict[str, Any] | None = None
    estimated_ltv_30d: float = 0.0
    estimated_ltv_90d: float = 0.0
    estimated_ltv_365d: float = 0.0
    confidence: float = 0.0
    sample_size: int = 0
    last_trained_at: str | None = None
    is_active: bool = True


class RevenueLeakRow(BaseModel):
    id: str
    leak_type: str
    affected_entity_type: str
    affected_entity_id: str | None = None
    estimated_leaked_revenue: float
    estimated_recoverable: float
    root_cause: str | None = None
    recommended_fix: str | None = None
    severity: str = "medium"
    details: dict[str, Any] | None = None


class LeaksDashboardResponse(BaseModel):
    brand_id: str
    funnel: dict[str, Any] = Field(default_factory=dict)
    leaks: list[RevenueLeakRow] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class GeoLanguageRecRow(BaseModel):
    id: str
    target_geography: str
    target_language: str
    target_platform: str | None = None
    estimated_audience_size: int = 0
    estimated_revenue_potential: float = 0.0
    entry_cost_estimate: float = 0.0
    rationale: str | None = None
    confidence: str = "medium"


class ExpansionRecommendationsResponse(BaseModel):
    geo_language_recommendations: list[GeoLanguageRecRow] = Field(default_factory=list)
    cross_platform_flow_plans: list[dict[str, Any]] = Field(default_factory=list)
    latest_expansion_decision_id: str | None = None


class PaidJobRow(BaseModel):
    id: str
    content_item_id: str
    platform: str
    budget: float
    spent: float
    status: str
    roi: float
    explanation: str | None = None
    is_candidate: bool = False


class PaidAmplificationResponse(BaseModel):
    jobs: list[PaidJobRow] = Field(default_factory=list)
    note: str = ""


class TrustReportRow(BaseModel):
    id: str
    creator_account_id: str | None = None
    trust_score: float
    components: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[Any] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    confidence_label: str = "medium"


class TrustSignalsResponse(BaseModel):
    reports: list[TrustReportRow] = Field(default_factory=list)


class GrowthIntelDashboardResponse(BaseModel):
    """Single-call bundle for the Growth Intel UI (optional convenience)."""

    brand_id: str
    audience_segments: list[AudienceSegmentResponse] = Field(default_factory=list)
    ltv_models: list[LtvModelResponse] = Field(default_factory=list)
    leaks: LeaksDashboardResponse
    expansion: ExpansionRecommendationsResponse
    paid_amplification: PaidAmplificationResponse
    trust_signals: TrustSignalsResponse
