"""Pydantic schemas for Affiliate Intelligence."""
from __future__ import annotations
import uuid
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

class AffiliateOfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; product_name: str; product_category: Optional[str] = None; offer_type: str; epc: float; conversion_rate: float; commission_rate: float; trust_score: float; rank_score: float; truth_label: str; blocker_state: Optional[str] = None; is_active: bool

class AffiliateLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; full_url: str; short_url: Optional[str] = None; platform: Optional[str] = None; click_count: int; conversion_count: int; disclosure_applied: bool

class AffiliateLeakOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; leak_type: str; severity: str; revenue_loss_estimate: float; recommendation: str

class AffiliateBlockerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; blocker_type: str; description: str; severity: str

class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0; status: str = "completed"
