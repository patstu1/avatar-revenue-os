"""Pydantic schemas for Phase 2 discovery endpoints."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SignalIngestRequest(BaseModel):
    source_type: str = "manual_seed"
    topics: list[dict] = []


class TopicCandidateResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    title: str
    description: Optional[str]
    keywords: Optional[list]
    category: Optional[str]
    estimated_search_volume: int
    trend_velocity: float
    relevance_score: float
    is_processed: bool
    is_rejected: bool
    rejection_reason: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class TrendSignalResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    platform: Optional[str]
    signal_type: str
    keyword: str
    volume: int
    velocity: float
    strength: str
    is_actionable: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class NicheClusterResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    cluster_name: str
    parent_niche: Optional[str]
    keywords: Optional[list]
    estimated_audience_size: int
    monetization_potential: float
    competition_density: float
    content_gap_score: float
    saturation_level: float
    recommended_entry_angle: Optional[str]
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class OpportunityScoreResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    topic_candidate_id: uuid.UUID
    composite_score: float
    trend_score: float
    audience_fit_score: float
    monetization_score: float
    competition_score: float
    originality_score: float
    saturation_penalty: float
    fatigue_penalty: float
    score_components: Optional[dict]
    confidence: str
    explanation: Optional[str]
    formula_version: str
    created_at: datetime
    model_config = {"from_attributes": True}


class OfferFitResponse(BaseModel):
    offer_id: uuid.UUID
    offer_name: str
    fit_score: float
    confidence: str
    explanation: str


class ForecastResponse(BaseModel):
    forecast_id: str
    expected_profit: float
    expected_revenue: float
    expected_cost: float
    rpm: float
    epc: float
    roi: float
    confidence: str
    explanation: str


class RecommendationResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    topic_candidate_id: Optional[uuid.UUID]
    offer_id: Optional[uuid.UUID]
    creator_account_id: Optional[uuid.UUID]
    rank: int
    composite_score: float
    recommended_action: str
    classification: str
    explanation: Optional[str]
    is_actioned: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class SaturationReportResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    creator_account_id: Optional[uuid.UUID]
    saturation_score: float
    fatigue_score: float
    originality_score: float
    topic_overlap_pct: float
    audience_overlap_pct: float
    recommended_action: str
    explanation: Optional[str]
    details: Optional[dict]
    created_at: datetime
    model_config = {"from_attributes": True}


class ProfitForecastResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    topic_candidate_id: Optional[uuid.UUID]
    offer_id: Optional[uuid.UUID]
    estimated_impressions: int
    estimated_ctr: float
    estimated_conversion_rate: float
    estimated_revenue: float
    estimated_cost: float
    estimated_profit: float
    estimated_rpm: float
    estimated_epc: float
    confidence: str
    assumptions: Optional[dict]
    explanation: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}
