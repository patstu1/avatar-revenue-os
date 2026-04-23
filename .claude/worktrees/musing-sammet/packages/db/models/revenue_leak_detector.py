"""Revenue Leak Detector — detect, cluster, estimate, correct."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class RevenueLeakReport(Base):
    __tablename__ = "rld_reports"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    total_leaks: Mapped[int] = mapped_column(Integer, default=0)
    total_estimated_loss: Mapped[float] = mapped_column(Float, default=0.0)
    critical_count: Mapped[int] = mapped_column(Integer, default=0)
    top_leak_type: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RevenueLeakEvent(Base):
    __tablename__ = "rld_events"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rld_reports.id"), nullable=False, index=True)
    leak_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    affected_scope: Mapped[str] = mapped_column(String(60), nullable=False)
    affected_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    estimated_revenue_loss: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    evidence_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    next_best_action: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    truth_label: Mapped[str] = mapped_column(String(40), default="measured")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LeakCluster(Base):
    __tablename__ = "rld_clusters"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    cluster_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    total_loss: Mapped[float] = mapped_column(Float, default=0.0)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LeakCorrectionAction(Base):
    __tablename__ = "rld_corrections"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    leak_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rld_events.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    action_detail: Mapped[str] = mapped_column(Text, nullable=False)
    target_system: Mapped[str] = mapped_column(String(60), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RevenueLossEstimate(Base):
    __tablename__ = "rld_loss_estimates"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(30), nullable=False)
    total_estimated_loss: Mapped[float] = mapped_column(Float, default=0.0)
    by_leak_type: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    by_scope: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
