"""Pydantic schemas for Brand Governance."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class BGProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; tone_profile: str | None = None; governance_level: str; language: str

class BGVoiceRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; rule_type: str; rule_key: str; severity: str; explanation: str | None = None

class BGViolationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; violation_type: str; severity: str; detail: str

class BGApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; approval_status: str; approved_by: str | None = None; notes: str | None = None

class BGKnowledgeBaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; kb_type: str; title: str; summary: str | None = None

class BGAudienceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; segment_name: str; trust_level: str; monetization_sensitivity: str

class BGAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; asset_type: str; asset_name: str; asset_url: str | None = None

class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0; status: str = "completed"
