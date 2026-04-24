"""Pydantic schemas for Revenue Leak Detector."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class RLDReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; total_leaks: int; total_estimated_loss: float; critical_count: int; top_leak_type: str | None = None; summary: str | None = None

class RLDEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; leak_type: str; severity: str; affected_scope: str; estimated_revenue_loss: float; confidence: float; next_best_action: str; status: str

class RLDClusterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; cluster_type: str; event_count: int; total_loss: float; priority_score: float; recommended_action: str | None = None

class RLDCorrectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; action_type: str; action_detail: str; target_system: str; priority: str

class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0; status: str = "completed"
