"""Pydantic schemas for Causal Attribution."""
from __future__ import annotations
import uuid
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

class CAReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; target_metric: str; direction: str; magnitude: float; top_driver: Optional[str] = None; total_hypotheses: int; summary: Optional[str] = None

class CAHypothesisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; driver_type: str; driver_name: str; estimated_lift_pct: float; confidence: float; recommended_action: Optional[str] = None

class CACreditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; driver_name: str; credit_pct: float; confidence: float; promote_cautiously: bool

class CAConfidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; hypothesis_count: int; high_confidence_count: int; noise_flagged_count: int; recommendation: Optional[str] = None

class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0; status: str = "completed"
