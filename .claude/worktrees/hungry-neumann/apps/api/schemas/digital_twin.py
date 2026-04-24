"""Pydantic schemas for Digital Twin."""
from __future__ import annotations
import uuid
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

class DTRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; run_name: str; scenario_count: int; total_expected_upside: float; summary: Optional[str] = None

class DTScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; scenario_type: str; option_label: str; compared_to: Optional[str] = None; expected_upside: float; expected_cost: float; expected_risk: float; confidence: float; time_to_signal_days: int; is_recommended: bool; explanation: Optional[str] = None

class DTRecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; scenario_type: str; recommended_action: str; expected_profit_delta: float; confidence: float; explanation: Optional[str] = None

class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0; status: str = "completed"
