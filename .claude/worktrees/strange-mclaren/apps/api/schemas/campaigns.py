"""Pydantic schemas for Campaigns."""
from __future__ import annotations
import uuid
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; campaign_type: str; campaign_name: str; objective: str; monetization_path: Optional[str] = None; budget_tier: str; expected_upside: float; expected_cost: float; confidence: float; launch_status: str; truth_label: str

class CampaignVariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; variant_label: str; hook_family: Optional[str] = None; cta_family: Optional[str] = None; is_control: bool

class CampaignBlockerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; blocker_type: str; description: str; severity: str

class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0; status: str = "completed"
