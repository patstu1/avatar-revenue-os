"""Pydantic schemas for Brain Architecture Phase A."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class BrainMemoryEntryOut(BaseModel):
    id: UUID
    brand_id: UUID
    entry_type: str
    scope_type: str
    scope_id: Optional[UUID] = None
    summary: str
    confidence: float
    reuse_recommendation: Optional[str] = None
    suppression_caution: Optional[str] = None
    platform: Optional[str] = None
    niche: Optional[str] = None
    detail_json: Optional[Any] = None
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BrainMemoryLinkOut(BaseModel):
    id: UUID
    brand_id: UUID
    source_entry_id: UUID
    target_entry_id: UUID
    link_type: str
    strength: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BrainMemoryBundleOut(BaseModel):
    entries: list[BrainMemoryEntryOut]
    links: list[BrainMemoryLinkOut]


class AccountStateSnapshotOut(BaseModel):
    id: UUID
    brand_id: UUID
    account_id: UUID
    current_state: str
    state_score: float
    previous_state: Optional[str] = None
    transition_reason: Optional[str] = None
    next_expected_state: Optional[str] = None
    days_in_state: int = 0
    platform: Optional[str] = None
    inputs_json: Optional[Any] = None
    confidence: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OpportunityStateSnapshotOut(BaseModel):
    id: UUID
    brand_id: UUID
    opportunity_scope: str
    opportunity_id: Optional[UUID] = None
    current_state: str
    urgency: float
    readiness: float
    suppression_risk: float
    expected_upside: float
    expected_cost: float
    inputs_json: Optional[Any] = None
    confidence: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ExecutionStateSnapshotOut(BaseModel):
    id: UUID
    brand_id: UUID
    execution_scope: str
    execution_id: Optional[UUID] = None
    current_state: str
    transition_reason: Optional[str] = None
    rollback_eligible: bool
    escalation_required: bool
    failure_count: int = 0
    inputs_json: Optional[Any] = None
    confidence: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AudienceStateSnapshotV2Out(BaseModel):
    id: UUID
    brand_id: UUID
    segment_label: str
    current_state: str
    state_score: float
    transition_likelihoods_json: Optional[Any] = None
    next_best_action: Optional[str] = None
    estimated_segment_size: int = 0
    estimated_ltv: float = 0.0
    inputs_json: Optional[Any] = None
    confidence: float
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class StateTransitionEventOut(BaseModel):
    id: UUID
    brand_id: UUID
    engine_type: str
    entity_id: UUID
    from_state: str
    to_state: str
    trigger: str
    confidence: float
    detail_json: Optional[Any] = None
    explanation: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: str
    counts: Optional[Any] = None
