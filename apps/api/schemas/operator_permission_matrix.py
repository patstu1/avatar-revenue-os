"""Pydantic schemas for Operator Permission Matrix."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class OPMMatrixOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    action_class: str
    autonomy_mode: str
    approval_role: str | None = None
    override_allowed: bool
    override_role: str | None = None
    explanation: str | None = None


class OPMExecutionModeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    action_class: str
    current_mode: str
    last_evaluated_reason: str | None = None


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    status: str = "completed"
