"""Pydantic schemas for Account Expansion Advisor."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ExpansionAdvisoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    should_add_account_now: bool
    platform: Optional[str] = None
    niche: Optional[str] = None
    sub_niche: Optional[str] = None
    account_type: Optional[str] = None
    content_role: Optional[str] = None
    monetization_path: Optional[str] = None
    expected_upside: float = 0.0
    expected_cost: float = 0.0
    expected_time_to_signal_days: int = 14
    confidence: float = 0.0
    urgency: float = 0.0
    explanation: str = ""
    hold_reason: Optional[str] = None
    blockers: Optional[list] = None
    evidence: Optional[dict] = None


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    should_add: bool = False
    status: str = "completed"
