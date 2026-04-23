"""Brain Architecture Pack — Phase A tables."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class BrainMemoryEntry(Base):
    __tablename__ = "brain_memory_entries"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reuse_recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suppression_caution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    platform: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    niche: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    detail_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BrainMemoryLink(Base):
    __tablename__ = "brain_memory_links"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    source_entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brain_memory_entries.id"), nullable=False, index=True)
    target_entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brain_memory_entries.id"), nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    strength: Mapped[float] = mapped_column(Float, default=0.5)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AccountStateSnapshot(Base):
    __tablename__ = "account_state_snapshots"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=False, index=True)
    current_state: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    state_score: Mapped[float] = mapped_column(Float, default=0.0)
    previous_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    transition_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_expected_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    days_in_state: Mapped[int] = mapped_column(Integer, default=0)
    platform: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    inputs_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OpportunityStateSnapshot(Base):
    __tablename__ = "opportunity_state_snapshots"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    opportunity_scope: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    current_state: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    urgency: Mapped[float] = mapped_column(Float, default=0.0)
    readiness: Mapped[float] = mapped_column(Float, default=0.0)
    suppression_risk: Mapped[float] = mapped_column(Float, default=0.0)
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    expected_cost: Mapped[float] = mapped_column(Float, default=0.0)
    inputs_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExecutionStateSnapshot(Base):
    __tablename__ = "execution_state_snapshots"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    execution_scope: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    current_state: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    transition_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rollback_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_required: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    inputs_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AudienceStateSnapshotV2(Base):
    __tablename__ = "audience_state_snapshots"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    segment_label: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    current_state: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    state_score: Mapped[float] = mapped_column(Float, default=0.0)
    transition_likelihoods_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    next_best_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_segment_size: Mapped[int] = mapped_column(Integer, default=0)
    estimated_ltv: Mapped[float] = mapped_column(Float, default=0.0)
    inputs_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class StateTransitionEvent(Base):
    __tablename__ = "state_transition_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    engine_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    from_state: Mapped[str] = mapped_column(String(60), nullable=False)
    to_state: Mapped[str] = mapped_column(String(60), nullable=False)
    trigger: Mapped[str] = mapped_column(String(200), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    detail_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
