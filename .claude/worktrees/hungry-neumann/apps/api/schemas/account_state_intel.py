"""Pydantic schemas for Account-State Intelligence."""
from __future__ import annotations
import uuid
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class AccountStateReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    account_id: uuid.UUID
    current_state: str
    confidence: float
    next_best_move: Optional[str] = None
    blocked_actions: Optional[Any] = None
    suitable_content_forms: Optional[Any] = None
    monetization_intensity: str
    posting_cadence: str
    expansion_eligible: bool
    explanation: Optional[str] = None


class AccountStateTransitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    account_id: uuid.UUID
    from_state: str
    to_state: str
    trigger: str
    confidence: float


class AccountStateActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    action_type: str
    action_detail: Optional[str] = None
    priority: str


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    status: str = "completed"
