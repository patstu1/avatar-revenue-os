"""Pydantic schemas for MXP Creative Memory."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CreativeMemoryAtomOut(BaseModel):
    id: str
    brand_id: str
    atom_type: str
    content_json: Optional[dict] = None
    niche: Optional[str] = None
    audience_segment_id: Optional[str] = None
    platform: Optional[str] = None
    monetization_type: Optional[str] = None
    account_type: Optional[str] = None
    funnel_stage: Optional[str] = None
    performance_summary_json: Optional[dict] = None
    reuse_recommendations_json: Optional[list] = None
    originality_caution_score: float
    confidence_score: float
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
