"""Pydantic schemas for Account Expansion Advisor."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class ExpansionAdvisoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    should_add_account_now: bool
    platform: str | None = None
    niche: str | None = None
    sub_niche: str | None = None
    account_type: str | None = None
    content_role: str | None = None
    monetization_path: str | None = None
    expected_upside: float = 0.0
    expected_cost: float = 0.0
    expected_time_to_signal_days: int = 14
    confidence: float = 0.0
    urgency: float = 0.0
    explanation: str = ""
    hold_reason: str | None = None
    blockers: list | None = None
    evidence: dict | None = None


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    should_add: bool = False
    status: str = "completed"
