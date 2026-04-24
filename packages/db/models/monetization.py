"""Monetization Machine Models — Credits, meters, plans, packs, telemetry."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class CreditLedger(Base):
    """Credit balance and transaction ledger per organization."""

    __tablename__ = "credit_ledgers"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    total_credits: Mapped[int] = mapped_column(Integer, default=0)
    used_credits: Mapped[int] = mapped_column(Integer, default=0)
    remaining_credits: Mapped[int] = mapped_column(Integer, default=0)
    bonus_credits: Mapped[int] = mapped_column(Integer, default=0)
    replenishment_rate: Mapped[int] = mapped_column(Integer, default=0)
    overage_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    overage_rate: Mapped[float] = mapped_column(Float, default=0.10)
    next_replenishment_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CreditTransaction(Base):
    """Individual credit transaction (earn, spend, purchase, expire)."""

    __tablename__ = "credit_transactions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    transaction_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, default=0)
    meter_type: Mapped[Optional[str]] = mapped_column(String(60), index=True)
    reference_id: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    transacted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UsageMeterSnapshot(Base):
    """Periodic usage meter snapshot for billing and analytics."""

    __tablename__ = "usage_meter_snapshots"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    meter_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    period_start: Mapped[str] = mapped_column(String(10), nullable=False)
    period_end: Mapped[str] = mapped_column(String(10), nullable=False)
    units_used: Mapped[int] = mapped_column(Integer, default=0)
    units_limit: Mapped[int] = mapped_column(Integer, default=0)
    utilization_pct: Mapped[float] = mapped_column(Float, default=0.0)
    overage_units: Mapped[int] = mapped_column(Integer, default=0)
    overage_cost: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PlanSubscription(Base):
    """Organization's active pricing plan."""

    __tablename__ = "plan_subscriptions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_tier: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    plan_name: Mapped[str] = mapped_column(String(120), nullable=False)
    monthly_price: Mapped[float] = mapped_column(Float, default=0.0)
    billing_interval: Mapped[str] = mapped_column(String(20), default="monthly")
    included_credits: Mapped[int] = mapped_column(Integer, default=0)
    max_seats: Mapped[int] = mapped_column(Integer, default=1)
    max_brands: Mapped[int] = mapped_column(Integer, default=1)
    features_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    meter_limits_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PackPurchase(Base):
    """One-time pack purchase (credit pack or outcome pack)."""

    __tablename__ = "pack_purchases"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    pack_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    pack_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    pack_name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    credits_awarded: Mapped[int] = mapped_column(Integer, default=0)
    items_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    stripe_payment_id: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="completed", index=True)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MultiplicationEvent(Base):
    """Revenue multiplication event (premium upgrade moments)."""

    __tablename__ = "multiplication_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    trigger_context: Mapped[Optional[str]] = mapped_column(Text)
    offered: Mapped[bool] = mapped_column(Boolean, default=True)
    converted: Mapped[bool] = mapped_column(Boolean, default=False)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    offered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    converted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MonetizationTelemetryEvent(Base):
    """Fine-grained telemetry for monetization intelligence."""

    __tablename__ = "monetization_telemetry"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    event_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    event_value: Mapped[float] = mapped_column(Float, default=0.0)
    event_properties: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    session_id: Mapped[Optional[str]] = mapped_column(String(255))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
