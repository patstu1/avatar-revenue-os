"""Pydantic schemas for Revenue Ceiling Phase A APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OfferLadderOut(BaseModel):
    id: str
    opportunity_key: str
    content_item_id: str | None = None
    offer_id: str | None = None
    top_of_funnel_asset: str = ""
    first_monetization_step: str = ""
    second_monetization_step: str = ""
    upsell_path: dict[str, Any] | None = None
    retention_path: dict[str, Any] | None = None
    fallback_path: dict[str, Any] | None = None
    ladder_recommendation: str | None = None
    expected_first_conversion_value: float = 0.0
    expected_downstream_value: float = 0.0
    expected_ltv_contribution: float = 0.0
    friction_level: str = "medium"
    confidence: float = 0.0
    explanation: str | None = None


class OwnedAudienceAssetOut(BaseModel):
    id: str
    asset_type: str
    channel_name: str = ""
    content_family: str | None = None
    objective_per_family: dict[str, Any] | None = None
    cta_variants: list | None = None
    estimated_channel_value: float = 0.0
    direct_vs_capture_score: float = 0.5


class OwnedAudienceEventOut(BaseModel):
    id: str
    content_item_id: str | None = None
    asset_id: str | None = None
    event_type: str
    value_contribution: float = 0.0
    source_metadata: dict[str, Any] | None = None
    created_at: str | None = None


class OwnedAudienceBundleResponse(BaseModel):
    assets: list[OwnedAudienceAssetOut] = Field(default_factory=list)
    events: list[OwnedAudienceEventOut] = Field(default_factory=list)


class MessageSequenceStepOut(BaseModel):
    id: str
    step_order: int
    channel: str
    subject_or_title: str | None = None
    body_template: str | None = None
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
    period_start: str | None = None
    period_end: str | None = None


class FunnelLeakOut(BaseModel):
    id: str
    leak_type: str
    severity: str = "medium"
    affected_funnel_stage: str = ""
    affected_content_family: str | None = None
    suspected_cause: str | None = None
    recommended_fix: str | None = None
    expected_upside: float = 0.0
    confidence: float = 0.0
    urgency: float = 0.0
