"""Brain Architecture Pack — Phase C tables: agent mesh, workflows, context bus, memory binding."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class AgentRegistryEntry(Base):
    __tablename__ = "agent_registry"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    agent_slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    agent_label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_schema_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    output_schema_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    memory_scopes_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    upstream_agents_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    downstream_agents_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AgentRunV2(Base):
    __tablename__ = "agent_runs_v2"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    agent_slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    run_status: Mapped[str] = mapped_column(String(40), default="running", index=True)
    trigger: Mapped[str] = mapped_column(String(120), nullable=False)
    inputs_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    outputs_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    memory_refs_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AgentMessageV2(Base):
    __tablename__ = "agent_messages_v2"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs_v2.id"), nullable=False, index=True
    )
    agent_slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    message_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkflowCoordinationRun(Base):
    __tablename__ = "workflow_coordination_runs"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    workflow_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    sequence_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(40), default="running", index=True)
    handoff_events_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    failure_points_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    inputs_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    outputs_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CoordinationDecision(Base):
    __tablename__ = "coordination_decisions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_coordination_runs.id"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    from_agent: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    to_agent: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SharedContextEvent(Base):
    __tablename__ = "shared_context_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_module: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    target_modules_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
