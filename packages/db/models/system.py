"""System tables: suppression actions, audit logs, system jobs, provider costs."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.enums import JobStatus, SuppressionReason


class SuppressionAction(Base):
    __tablename__ = "suppression_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    target_entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    reason: Mapped[SuppressionReason] = mapped_column(Enum(SuppressionReason), nullable=False)
    reason_detail: Mapped[Optional[str]] = mapped_column(Text)
    decision_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    suppressed_by: Mapped[str] = mapped_column(String(50), default="system")
    suppressed_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_permanent: Mapped[bool] = mapped_column(default=False)
    is_lifted: Mapped[bool] = mapped_column(default=False)
    lifted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    lifted_reason: Mapped[Optional[str]] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), index=True
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), index=True)
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False, default="system")
    action: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    details: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))


class SystemJob(Base):
    __tablename__ = "system_jobs"

    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), index=True)
    job_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    queue: Mapped[str] = mapped_column(String(100), default="default")
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING, index=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255))
    input_params: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    output_result: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_traceback: Mapped[Optional[str]] = mapped_column(Text)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)


class ProviderUsageCost(Base):
    __tablename__ = "provider_usage_costs"

    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)
    operation: Mapped[str] = mapped_column(String(255), nullable=False)
    input_units: Mapped[int] = mapped_column(Integer, default=0)
    output_units: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    related_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    raw_usage: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
