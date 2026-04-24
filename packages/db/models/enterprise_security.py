"""Enterprise Security + Compliance OS — RBAC, audit, data policies, compliance."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class EnterpriseRole(Base):
    __tablename__ = "es_roles"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    role_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    role_level: Mapped[int] = mapped_column(Integer, default=50)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class EnterprisePermission(Base):
    __tablename__ = "es_permissions"
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("es_roles.id"), nullable=False, index=True
    )
    permission_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(60), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class EnterpriseUserGroup(Base):
    __tablename__ = "es_user_groups"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    group_name: Mapped[str] = mapped_column(String(120), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("es_roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class EnterpriseAccessScope(Base):
    __tablename__ = "es_access_scopes"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("es_roles.id"), nullable=False)
    granted_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditTrailEvent(Base):
    __tablename__ = "es_audit_trail"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    before_state: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    after_state: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SensitiveDataPolicy(Base):
    __tablename__ = "es_sensitive_data_policies"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    policy_name: Mapped[str] = mapped_column(String(120), nullable=False)
    data_class: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    restricted_fields: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    masking_rules: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    model_restriction: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    private_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    training_leak_prevention: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ModelIsolationPolicy(Base):
    __tablename__ = "es_model_isolation"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    provider_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    isolation_mode: Mapped[str] = mapped_column(String(30), default="shared")
    dedicated_instance_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    data_residency: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ComplianceControlReport(Base):
    __tablename__ = "es_compliance_controls"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    framework: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    control_id: Mapped[str] = mapped_column(String(60), nullable=False)
    control_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="not_assessed")
    evidence: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RiskOverrideEvent(Base):
    __tablename__ = "es_risk_overrides"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    override_type: Mapped[str] = mapped_column(String(60), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(60), nullable=False)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
