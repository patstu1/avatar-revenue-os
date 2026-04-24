"""Pydantic schemas for Brand Governance."""
from __future__ import annotations
import uuid
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict

class BGProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; tone_profile: Optional[str] = None; governance_level: str; language: str

class BGVoiceRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; rule_type: str; rule_key: str; severity: str; explanation: Optional[str] = None

class BGViolationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; violation_type: str; severity: str; detail: str

class BGApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; approval_status: str; approved_by: Optional[str] = None; notes: Optional[str] = None

class BGKnowledgeBaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; kb_type: str; title: str; summary: Optional[str] = None

class BGAudienceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; segment_name: str; trust_level: str; monetization_sensitivity: str

class BGAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; asset_type: str; asset_name: str; asset_url: Optional[str] = None

class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0; status: str = "completed"
