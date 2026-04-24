"""Hyper-Scale Execution OS — capacity, queues, bursts, ceilings, degradation."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class ExecutionCapacityReport(Base):
    __tablename__ = "hs_capacity_reports"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    total_queued: Mapped[int] = mapped_column(Integer, default=0)
    total_running: Mapped[int] = mapped_column(Integer, default=0)
    total_completed_24h: Mapped[int] = mapped_column(Integer, default=0)
    throughput_per_hour: Mapped[float] = mapped_column(Float, default=0.0)
    avg_latency_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    burst_active: Mapped[bool] = mapped_column(Boolean, default=False)
    degraded: Mapped[bool] = mapped_column(Boolean, default=False)
    health_status: Mapped[str] = mapped_column(String(20), default="healthy")
    summary_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExecutionQueueSegment(Base):
    __tablename__ = "hs_queue_segments"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    segment_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    segment_type: Mapped[str] = mapped_column(String(40), nullable=False)
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)
    queue_depth: Mapped[int] = mapped_column(Integer, default=0)
    running_count: Mapped[int] = mapped_column(Integer, default=0)
    max_concurrency: Mapped[int] = mapped_column(Integer, default=10)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkloadAllocation(Base):
    __tablename__ = "hs_workload_allocations"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True, index=True)
    allocation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    allocated_capacity: Mapped[int] = mapped_column(Integer, default=0)
    used_capacity: Mapped[int] = mapped_column(Integer, default=0)
    market: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ThroughputEvent(Base):
    __tablename__ = "hs_throughput_events"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(30), nullable=False)
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    tasks_failed: Mapped[int] = mapped_column(Integer, default=0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    cost_incurred: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BurstEvent(Base):
    __tablename__ = "hs_burst_events"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    burst_type: Mapped[str] = mapped_column(String(40), nullable=False)
    peak_qps: Mapped[float] = mapped_column(Float, default=0.0)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    tasks_queued: Mapped[int] = mapped_column(Integer, default=0)
    degradation_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UsageCeilingRule(Base):
    __tablename__ = "hs_usage_ceilings"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)
    ceiling_type: Mapped[str] = mapped_column(String(40), nullable=False)
    max_value: Mapped[float] = mapped_column(Float, default=0.0)
    current_value: Mapped[float] = mapped_column(Float, default=0.0)
    period: Mapped[str] = mapped_column(String(20), default="monthly")
    enforced: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class DegradationEvent(Base):
    __tablename__ = "hs_degradation_events"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    degradation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False)
    action_taken: Mapped[str] = mapped_column(Text, nullable=False)
    recovered: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ScaleHealthReport(Base):
    __tablename__ = "hs_scale_health"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    health_status: Mapped[str] = mapped_column(String(20), default="healthy")
    queue_depth_total: Mapped[int] = mapped_column(Integer, default=0)
    ceiling_utilization_pct: Mapped[float] = mapped_column(Float, default=0.0)
    burst_count_24h: Mapped[int] = mapped_column(Integer, default=0)
    degradation_count_24h: Mapped[int] = mapped_column(Integer, default=0)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
