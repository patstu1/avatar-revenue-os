"""Pydantic schemas for Recovery Engine."""
from __future__ import annotations
import uuid
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

class RECIncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; incident_type: str; severity: str; affected_scope: str; detail: str; auto_recoverable: bool; recovery_status: str

class RECRollbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; rollback_type: str; rollback_target: str; execution_status: str

class RECRerouteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; from_path: str; to_path: str; reason: str; execution_status: str

class RECThrottleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; throttle_target: str; throttle_level: str; reason: str; execution_status: str

class RECOutcomeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; outcome_type: str; success: bool; time_to_recover_minutes: int

class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0; status: str = "completed"
