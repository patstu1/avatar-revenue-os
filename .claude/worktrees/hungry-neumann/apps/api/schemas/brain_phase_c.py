"""Pydantic schemas for Brain Architecture Phase C."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class AgentRegistryOut(BaseModel):
    id: UUID
    brand_id: UUID
    agent_slug: str
    agent_label: str
    description: Optional[str] = None
    input_schema_json: Optional[Any] = None
    output_schema_json: Optional[Any] = None
    memory_scopes_json: Optional[Any] = None
    upstream_agents_json: Optional[Any] = None
    downstream_agents_json: Optional[Any] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AgentRunV2Out(BaseModel):
    id: UUID
    brand_id: UUID
    agent_slug: str
    run_status: str
    trigger: str
    inputs_json: Optional[Any] = None
    outputs_json: Optional[Any] = None
    memory_refs_json: Optional[Any] = None
    confidence: float
    duration_ms: int
    error_detail: Optional[str] = None
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkflowCoordinationRunOut(BaseModel):
    id: UUID
    brand_id: UUID
    workflow_type: str
    sequence_json: Optional[Any] = None
    status: str
    handoff_events_json: Optional[Any] = None
    failure_points_json: Optional[Any] = None
    inputs_json: Optional[Any] = None
    outputs_json: Optional[Any] = None
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SharedContextEventOut(BaseModel):
    id: UUID
    brand_id: UUID
    event_type: str
    source_module: str
    target_modules_json: Optional[Any] = None
    payload_json: Optional[Any] = None
    priority: int
    consumed: bool
    explanation: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: str
    counts: Optional[Any] = None
