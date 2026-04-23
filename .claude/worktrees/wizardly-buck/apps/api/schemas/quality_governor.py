"""Pydantic schemas for Quality Governor."""
from __future__ import annotations
import uuid
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class QGReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    content_item_id: uuid.UUID
    total_score: float
    verdict: str
    publish_allowed: bool
    confidence: float
    reasons: Optional[Any] = None


class QGDimensionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    dimension: str
    score: float
    max_score: float
    explanation: Optional[str] = None


class QGBlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    content_item_id: uuid.UUID
    block_reason: str
    severity: str


class QGImprovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    dimension: str
    action: str
    priority: str


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    status: str = "completed"
