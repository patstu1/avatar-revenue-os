"""SaaS metrics, subscriptions, pipeline, and pricing models."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class Subscription(Base):
    """Tracks individual subscriptions (SaaS, membership, community)."""
    __tablename__ = "subscriptions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    customer_email: Mapped[Optional[str]] = mapped_column(String(255))
    customer_name: Mapped[Optional[str]] = mapped_column(String(255))
    plan_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    plan_tier: Mapped[str] = mapped_column(String(60), default="standard", index=True)
    mrr: Mapped[float] = mapped_column(Float, default=0.0)
    billing_interval: Mapped[str] = mapped_column(String(20), default="monthly")
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SubscriptionEvent(Base):
    """Tracks subscription lifecycle events (new, upgrade, downgrade, churn, reactivation)."""
    __tablename__ = "subscription_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    old_mrr: Mapped[float] = mapped_column(Float, default=0.0)
    new_mrr: Mapped[float] = mapped_column(Float, default=0.0)
    mrr_delta: Mapped[float] = mapped_column(Float, default=0.0)
    old_plan: Mapped[Optional[str]] = mapped_column(String(120))
    new_plan: Mapped[Optional[str]] = mapped_column(String(120))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SaaSMetricSnapshot(Base):
    """Daily/weekly snapshot of SaaS metrics for trend tracking."""
    __tablename__ = "saas_metric_snapshots"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    snapshot_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    mrr: Mapped[float] = mapped_column(Float, default=0.0)
    arr: Mapped[float] = mapped_column(Float, default=0.0)
    new_mrr: Mapped[float] = mapped_column(Float, default=0.0)
    churned_mrr: Mapped[float] = mapped_column(Float, default=0.0)
    expansion_mrr: Mapped[float] = mapped_column(Float, default=0.0)
    contraction_mrr: Mapped[float] = mapped_column(Float, default=0.0)
    net_new_mrr: Mapped[float] = mapped_column(Float, default=0.0)
    active_subscriptions: Mapped[int] = mapped_column(Integer, default=0)
    churned_subscriptions: Mapped[int] = mapped_column(Integer, default=0)
    new_subscriptions: Mapped[int] = mapped_column(Integer, default=0)
    gross_churn_rate: Mapped[float] = mapped_column(Float, default=0.0)
    net_revenue_retention: Mapped[float] = mapped_column(Float, default=1.0)
    ltv: Mapped[float] = mapped_column(Float, default=0.0)
    cac: Mapped[float] = mapped_column(Float, default=0.0)
    quick_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class HighTicketDeal(Base):
    """Tracks high-ticket sales pipeline (consulting, services, courses)."""
    __tablename__ = "high_ticket_deals"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_email: Mapped[Optional[str]] = mapped_column(String(255))
    deal_value: Mapped[float] = mapped_column(Float, default=0.0)
    stage: Mapped[str] = mapped_column(String(60), default="awareness", index=True)
    product_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(60), default="content", index=True)
    probability: Mapped[float] = mapped_column(Float, default=0.1)
    expected_close_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    interactions: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProductLaunch(Base):
    """Tracks digital product/course launches."""
    __tablename__ = "product_launches"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    launch_phase: Mapped[str] = mapped_column(String(40), default="planning", index=True)
    registrations: Mapped[int] = mapped_column(Integer, default=0)
    sales: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    ad_spend: Mapped[float] = mapped_column(Float, default=0.0)
    launch_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    close_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    funnel_metrics_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    launch_plan_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
