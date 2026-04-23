"""Pydantic schemas for Revenue Ceiling Phase A APIs."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class OfferLadderOut(BaseModel):
    id: str
    opportunity_key: str
    content_item_id: Optional[str] = None
    offer_id: Optional[str] = None
    top_of_funnel_asset: str = ""
    first_monetization_step: str = ""
    second_monetization_step: str = ""
    upsell_path: Optional[dict[str, Any]] = None
    retention_path: Optional[dict[str, Any]] = None
    fallback_path: Optional[dict[str, Any]] = None
    ladder_recommendation: Optional[str] = None
    expected_first_conversion_value: float = 0.0
    expected_downstream_value: float = 0.0
    expected_ltv_contribution: float = 0.0
    friction_level: str = "medium"
    confidence: float = 0.0
    explanation: Optional[str] = None


class OwnedAudienceAssetOut(BaseModel):
    id: str
    asset_type: str
    channel_name: str = ""
    content_family: Optional[str] = None
    objective_per_family: Optional[dict[str, Any]] = None
    cta_variants: Optional[list] = None
    estimated_channel_value: float = 0.0
    direct_vs_capture_score: float = 0.5


class OwnedAudienceEventOut(BaseModel):
    id: str
    content_item_id: Optional[str] = None
    asset_id: Optional[str] = None
    event_type: str
    value_contribution: float = 0.0
    source_metadata: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None


class OwnedAudienceBundleResponse(BaseModel):
    assets: list[OwnedAudienceAssetOut] = Field(default_factory=list)
    events: list[OwnedAudienceEventOut] = Field(default_factory=list)


class MessageSequenceStepOut(BaseModel):
    id: str
    step_order: int
    channel: str
    subject_or_title: Optional[str] = None
    body_template: Optional[str] = None
    delay_hours_after_previous: int = 0


class MessageSequenceOut(BaseModel):
    id: str
    sequence_type: str
    channel: str
    title: str = ""
    sponsor_safe: bool = False
    steps: list[MessageSequenceStepOut] = Field(default_factory=list)


class FunnelStageMetricOut(BaseModel):
    id: str
    content_family: str
    stage: str
    metric_value: float
    sample_size: int
    period_start: Optional[str] = None
    period_end: Optional[str] = None


class FunnelLeakOut(BaseModel):
    id: str
    leak_type: str
    severity: str = "medium"
    affected_funnel_stage: str = ""
    affected_content_family: Optional[str] = None
    suspected_cause: Optional[str] = None
    recommended_fix: Optional[str] = None
    expected_upside: float = 0.0
    confidence: float = 0.0
    urgency: float = 0.0
