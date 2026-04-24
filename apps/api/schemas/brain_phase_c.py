"""Pydantic schemas for Brain Architecture Phase C."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AgentRegistryOut(BaseModel):
    id: UUID
    brand_id: UUID
    agent_slug: str
    agent_label: str
    description: str | None = None
    input_schema_json: Any | None = None
    output_schema_json: Any | None = None
    memory_scopes_json: Any | None = None
    upstream_agents_json: Any | None = None
    downstream_agents_json: Any | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentRunV2Out(BaseModel):
    id: UUID
    brand_id: UUID
    agent_slug: str
    run_status: str
    trigger: str
    inputs_json: Any | None = None
    outputs_json: Any | None = None
    memory_refs_json: Any | None = None
    confidence: float
    duration_ms: int
    error_detail: str | None = None
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class WorkflowCoordinationRunOut(BaseModel):
    id: UUID
    brand_id: UUID
    workflow_type: str
    sequence_json: Any | None = None
    status: str
    handoff_events_json: Any | None = None
    failure_points_json: Any | None = None
    inputs_json: Any | None = None
    outputs_json: Any | None = None
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SharedContextEventOut(BaseModel):
    id: UUID
    brand_id: UUID
    event_type: str
    source_module: str
    target_modules_json: Any | None = None
    payload_json: Any | None = None
    priority: int
    consumed: bool
    explanation: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class RecomputeSummaryOut(BaseModel):
    status: str
    detail: str
    counts: Any | None = None
