"""Pydantic schemas for Enterprise Affiliate."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class AFGovRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; rule_type: str; rule_key: str; severity: str; explanation: str | None = None

class AFBannedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; entity_type: str; entity_name: str; reason: str

class AFApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; entity_type: str; approval_status: str; notes: str | None = None

class AFRiskFlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; risk_type: str; risk_score: float; detail: str

class AFPartnerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; partner_name: str; partner_status: str; partner_score: float; conversion_quality: float; fraud_risk: float; total_conversions: int; total_revenue_generated: float

class RecomputeSummaryOut(BaseModel):
    rows_processed: int = 0; status: str = "completed"
