"""Executive Intelligence + Service Layer — KPIs, forecasts, costs, uptime, oversight."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class ExecutiveKPIReport(Base):
    __tablename__ = "ei_kpi_reports"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True, index=True)
    period: Mapped[str] = mapped_column(String(30), nullable=False)
    total_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    total_profit: Mapped[float] = mapped_column(Float, default=0.0)
    total_spend: Mapped[float] = mapped_column(Float, default=0.0)
    content_produced: Mapped[int] = mapped_column(Integer, default=0)
    content_published: Mapped[int] = mapped_column(Integer, default=0)
    total_impressions: Mapped[float] = mapped_column(Float, default=0.0)
    avg_engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    active_accounts: Mapped[int] = mapped_column(Integer, default=0)
    active_campaigns: Mapped[int] = mapped_column(Integer, default=0)
    kpi_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExecutiveForecast(Base):
    __tablename__ = "ei_forecasts"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)
    forecast_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    forecast_period: Mapped[str] = mapped_column(String(30), nullable=False)
    predicted_value: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    risk_factors: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    opportunity_factors: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UsageCostReport(Base):
    __tablename__ = "ei_usage_cost"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)
    period: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    tasks_executed: Mapped[int] = mapped_column(Integer, default=0)
    cost_incurred: Mapped[float] = mapped_column(Float, default=0.0)
    cost_by_tier: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProviderUptimeReport(Base):
    __tablename__ = "ei_provider_uptime"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    provider_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(30), nullable=False)
    uptime_pct: Mapped[float] = mapped_column(Float, default=100.0)
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    failed_requests: Mapped[int] = mapped_column(Integer, default=0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    reliability_grade: Mapped[str] = mapped_column(String(5), default="A")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OversightModeReport(Base):
    __tablename__ = "ei_oversight_mode"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(30), default="hybrid")
    auto_approved_count: Mapped[int] = mapped_column(Integer, default=0)
    human_reviewed_count: Mapped[int] = mapped_column(Integer, default=0)
    override_count: Mapped[int] = mapped_column(Integer, default=0)
    ai_accuracy_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ServiceHealthReport(Base):
    __tablename__ = "ei_service_health"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    service_name: Mapped[str] = mapped_column(String(80), nullable=False)
    health_status: Mapped[str] = mapped_column(String(20), default="healthy")
    active_issues: Mapped[int] = mapped_column(Integer, default=0)
    last_incident: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExecutiveAlert(Base):
    __tablename__ = "ei_alerts"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
