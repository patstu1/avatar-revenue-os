"""Provider Registry — source of truth for all API/connector/provider integrations."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class ProviderRegistryEntry(Base):
    __tablename__ = "provider_registry"

    provider_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    env_keys: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    credential_status: Mapped[str] = mapped_column(String(30), default="not_configured", index=True)
    integration_status: Mapped[str] = mapped_column(String(30), default="stubbed", index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)
    capabilities_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    config_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProviderCapability(Base):
    __tablename__ = "provider_capabilities"

    provider_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    capability: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProviderDependency(Base):
    __tablename__ = "provider_dependencies"

    provider_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    module_path: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    dependency_type: Mapped[str] = mapped_column(String(40), default="required", index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProviderReadinessReport(Base):
    __tablename__ = "provider_readiness_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    provider_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    credential_status: Mapped[str] = mapped_column(String(30), default="not_configured", index=True)
    integration_status: Mapped[str] = mapped_column(String(30), default="stubbed", index=True)
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    missing_env_keys: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    operator_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProviderUsageEvent(Base):
    __tablename__ = "provider_usage_events"

    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True, index=True)
    provider_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProviderBlocker(Base):
    __tablename__ = "provider_blockers"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    provider_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    blocker_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(30), default="high", index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    operator_action_needed: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
