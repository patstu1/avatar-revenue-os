"""Pydantic schemas for Offer Lab."""
from __future__ import annotations
import uuid
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

class OLOfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; offer_name: str; offer_type: str; primary_angle: Optional[str] = None; price_point: float; rank_score: float; confidence: float; status: str; truth_label: str

class OLVariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; variant_type: str; variant_name: str; angle: Optional[str] = None; price_point: float; is_control: bool; performance_score: float

class OLBundleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; bundle_name: str; combined_price: float; savings_pct: float; expected_uplift: float

class OLBlockerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; blocker_type: str; description: str; recommendation: Optional[str] = None; severity: str

class OLLearningOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; learning_type: str; measured_metric: str; measured_value: float; previous_value: float; insight: Optional[str] = None

class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0; status: str = "completed"
