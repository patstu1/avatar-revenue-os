"""Pydantic schemas for Winning-Pattern Memory."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class WinningPatternOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pattern_type: str
    pattern_name: str
    platform: str | None = None
    niche: str | None = None
    content_form: str | None = None
    monetization_method: str | None = None
    performance_band: str
    confidence: float
    win_score: float
    decay_score: float
    usage_count: int
    explanation: str | None = None


class PatternClusterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cluster_name: str
    cluster_type: str
    platform: str | None = None
    avg_win_score: float
    pattern_count: int
    explanation: str | None = None


class LosingPatternOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pattern_type: str
    pattern_name: str
    platform: str | None = None
    fail_score: float
    suppress_reason: str | None = None


class PatternReuseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_platform: str
    target_content_form: str | None = None
    expected_uplift: float
    confidence: float
    explanation: str | None = None


class PatternDecayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    decay_rate: float
    decay_reason: str
    previous_win_score: float
    current_win_score: float
    recommendation: str | None = None


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    status: str = "completed"
