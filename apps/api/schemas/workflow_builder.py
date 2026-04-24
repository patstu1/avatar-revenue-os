"""Pydantic schemas for Workflow Builder."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class WFDefinitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workflow_name: str
    workflow_type: str
    scope_type: str
    is_active: bool


class WFInstanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    resource_type: str
    current_step_order: int
    status: str


class WFApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    notes: str | None = None


class WFRejectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    reason: str


class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0
    status: str = "completed"
