"""Pydantic schemas for Winning-Pattern Memory."""
from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict


class WinningPatternOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pattern_type: str
    pattern_name: str
    platform: Optional[str] = None
    niche: Optional[str] = None
    content_form: Optional[str] = None
    monetization_method: Optional[str] = None
    performance_band: str
    confidence: float
    win_score: float
    decay_score: float
    usage_count: int
    explanation: Optional[str] = None


class PatternClusterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cluster_name: str
    cluster_type: str
    platform: Optional[str] = None
    avg_win_score: float
    pattern_count: int
    explanation: Optional[str] = None


class LosingPatternOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pattern_type: str
    pattern_name: str
    platform: Optional[str] = None
    fail_score: float
    suppress_reason: Optional[str] = None


class PatternReuseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_platform: str
    target_content_form: Optional[str] = None
    expected_uplift: float
    confidence: float
    explanation: Optional[str] = None


class PatternDecayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    decay_rate: float
    decay_reason: str
    previous_win_score: float
    current_win_score: float
    recommendation: Optional[str] = None


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    status: str = "completed"
