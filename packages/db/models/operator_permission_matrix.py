"""Operator Permission Matrix — autonomy levels by action class."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class OperatorPermissionMatrix(Base):
    __tablename__ = "opm_matrix"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)
    action_class: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    autonomy_mode: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    approval_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    override_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    override_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AutonomyActionPolicy(Base):
    __tablename__ = "opm_action_policies"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    action_class: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    default_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    conditions_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    escalation_path: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ActionApprovalRequirement(Base):
    __tablename__ = "opm_approval_requirements"
    matrix_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opm_matrix.id"), nullable=False, index=True
    )
    required_role: Mapped[str] = mapped_column(String(80), nullable=False)
    min_role_level: Mapped[int] = mapped_column(Integer, default=50)
    timeout_hours: Mapped[int] = mapped_column(Integer, default=24)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ActionOverrideRule(Base):
    __tablename__ = "opm_override_rules"
    matrix_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opm_matrix.id"), nullable=False, index=True
    )
    override_condition: Mapped[str] = mapped_column(String(120), nullable=False)
    allowed_role: Mapped[str] = mapped_column(String(80), nullable=False)
    reason_required: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ActionExecutionMode(Base):
    __tablename__ = "opm_execution_modes"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    action_class: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    current_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    last_evaluated_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
