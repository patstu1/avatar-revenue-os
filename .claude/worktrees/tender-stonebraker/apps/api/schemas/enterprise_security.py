"""Pydantic schemas for Enterprise Security."""
from __future__ import annotations
import uuid
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

class ESRoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; role_name: str; role_level: int; description: Optional[str] = None; is_system: bool

class ESPermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; permission_key: str; resource_type: str; action: str

class ESAuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; action: str; resource_type: str; detail: Optional[str] = None

class ESDataPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; policy_name: str; data_class: str; private_mode: bool; training_leak_prevention: bool

class ESComplianceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; framework: str; control_id: str; control_name: str; status: str

class ESModelIsolationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; provider_key: str; isolation_mode: str; data_residency: Optional[str] = None

class ESRiskOverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; override_type: str; resource_type: str; reason: str

class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0; status: str = "completed"
