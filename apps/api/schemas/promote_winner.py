"""Pydantic schemas for Promote-Winner Engine."""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict


class ActiveExperimentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    experiment_name: str
    hypothesis: str
    tested_variable: str
    target_platform: str | None = None
    primary_metric: str
    status: str
    explanation: str | None = None


class PWVariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    variant_name: str
    is_control: bool
    sample_count: int
    primary_metric_value: float


class PWWinnerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    win_margin: float
    confidence: float
    sample_size: int
    promoted: bool
    explanation: str | None = None


class PWLoserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    loss_margin: float
    suppressed: bool
    explanation: str | None = None


class PromotedRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    rule_type: str
    rule_key: str
    rule_value: Any | None = None
    target_platform: str | None = None
    weight_boost: float
    is_active: bool
    explanation: str | None = None


class CreateExperimentIn(BaseModel):
    experiment_name: str
    hypothesis: str
    tested_variable: str
    variant_configs: list[dict[str, Any]]
    primary_metric: str = "engagement_rate"
    min_sample_size: int = 30
    confidence_threshold: float = 0.90
    target_platform: str | None = None
    target_niche: str | None = None
    target_offer_id: uuid.UUID | None = None


class AddObservationIn(BaseModel):
    variant_id: uuid.UUID
    metric_name: str
    metric_value: float
    content_item_id: uuid.UUID | None = None


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    status: str = "completed"
