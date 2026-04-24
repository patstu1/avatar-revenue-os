"""Pydantic schemas for Account-State Intelligence."""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict


class AccountStateReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    account_id: uuid.UUID
    current_state: str
    confidence: float
    next_best_move: str | None = None
    blocked_actions: Any | None = None
    suitable_content_forms: Any | None = None
    monetization_intensity: str
    posting_cadence: str
    expansion_eligible: bool
    explanation: str | None = None


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
    action_detail: str | None = None
    priority: str


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    status: str = "completed"
