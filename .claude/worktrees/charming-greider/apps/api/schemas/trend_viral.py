"""Pydantic schemas for Trend / Viral Engine."""
from __future__ import annotations
import uuid
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

class TVSignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; source: str; topic: str; signal_strength: float; velocity: float; truth_label: str

class TVVelocityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; topic: str; current_velocity: float; acceleration: float; breakout: bool

class TVOpportunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; topic: str; source: str; velocity_score: float; novelty_score: float; revenue_potential_score: float; opportunity_type: str; recommended_platform: Optional[str] = None; recommended_content_form: Optional[str] = None; recommended_monetization: Optional[str] = None; urgency: float; confidence: float; composite_score: float; truth_label: str; status: str

class TVBlockerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; blocker_type: str; description: str; severity: str

class TVSourceHealthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; source_name: str; status: str; last_signal_count: int; truth_label: str

class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0; status: str = "completed"
