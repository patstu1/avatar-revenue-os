"""Recovery / Rollback Engine — detect, recover, throttle, reroute, rollback."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class RecoveryIncidentV2(Base):
    __tablename__ = "rec_incidents"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True, index=True
    )
    incident_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="high")
    affected_scope: Mapped[str] = mapped_column(String(60), nullable=False)
    affected_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    auto_recoverable: Mapped[bool] = mapped_column(Boolean, default=False)
    recovery_status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    playbook_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RollbackAction(Base):
    __tablename__ = "rec_rollbacks"
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rec_incidents.id"), nullable=False, index=True
    )
    rollback_type: Mapped[str] = mapped_column(String(40), nullable=False)
    rollback_target: Mapped[str] = mapped_column(String(120), nullable=False)
    previous_state: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    execution_status: Mapped[str] = mapped_column(String(20), default="pending")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RerouteAction(Base):
    __tablename__ = "rec_reroutes"
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rec_incidents.id"), nullable=False, index=True
    )
    from_path: Mapped[str] = mapped_column(String(255), nullable=False)
    to_path: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    execution_status: Mapped[str] = mapped_column(String(20), default="pending")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ThrottlingAction(Base):
    __tablename__ = "rec_throttles"
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rec_incidents.id"), nullable=False, index=True
    )
    throttle_target: Mapped[str] = mapped_column(String(120), nullable=False)
    throttle_level: Mapped[str] = mapped_column(String(20), default="50pct")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    execution_status: Mapped[str] = mapped_column(String(20), default="pending")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RecoveryOutcome(Base):
    __tablename__ = "rec_outcomes"
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rec_incidents.id"), nullable=False, index=True
    )
    outcome_type: Mapped[str] = mapped_column(String(40), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    time_to_recover_minutes: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RecoveryPlaybook(Base):
    __tablename__ = "rec_playbooks"
    playbook_name: Mapped[str] = mapped_column(String(120), nullable=False)
    incident_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    steps_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    auto_execute: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
