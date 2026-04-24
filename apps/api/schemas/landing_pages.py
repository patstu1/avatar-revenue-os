"""Pydantic schemas for Landing Pages."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class LandingPageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    page_type: str
    headline: str
    subheadline: str | None = None
    hook_angle: str | None = None
    status: str
    publish_status: str
    truth_label: str
    blocker_state: str | None = None
    destination_url: str | None = None


class LPVariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    variant_label: str
    headline: str
    hook_angle: str | None = None
    is_control: bool
    conversion_rate: float


class LPQualityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    total_score: float
    trust_score: float
    conversion_fit: float
    objection_coverage: float
    verdict: str


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    status: str = "completed"
