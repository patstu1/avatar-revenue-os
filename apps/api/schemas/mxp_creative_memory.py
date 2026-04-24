"""Pydantic schemas for MXP Creative Memory."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CreativeMemoryAtomOut(BaseModel):
    id: str
    brand_id: str
    atom_type: str
    content_json: dict | None = None
    niche: str | None = None
    audience_segment_id: str | None = None
    platform: str | None = None
    monetization_type: str | None = None
    account_type: str | None = None
    funnel_stage: str | None = None
    performance_summary_json: dict | None = None
    reuse_recommendations_json: list | None = None
    originality_caution_score: float
    confidence_score: float
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
