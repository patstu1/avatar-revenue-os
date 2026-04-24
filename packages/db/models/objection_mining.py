"""Objection Mining — detect, cluster, score, and route buyer resistance."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class ObjectionSignal(Base):
    __tablename__ = "om_objection_signals"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True
    )
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True)
    objection_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_objection: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[float] = mapped_column(Float, default=0.5)
    monetization_impact: Mapped[float] = mapped_column(Float, default=0.0)
    platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ObjectionCluster(Base):
    __tablename__ = "om_objection_clusters"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    objection_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    cluster_label: Mapped[str] = mapped_column(String(255), nullable=False)
    signal_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_severity: Mapped[float] = mapped_column(Float, default=0.0)
    avg_monetization_impact: Mapped[float] = mapped_column(Float, default=0.0)
    representative_texts: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    recommended_response_angle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ObjectionResponse(Base):
    __tablename__ = "om_objection_responses"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("om_objection_clusters.id"), nullable=False, index=True
    )
    response_type: Mapped[str] = mapped_column(String(60), nullable=False)
    response_angle: Mapped[str] = mapped_column(Text, nullable=False)
    target_channel: Mapped[str] = mapped_column(String(60), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ObjectionPriorityReport(Base):
    __tablename__ = "om_priority_reports"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    top_objections: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    total_signals: Mapped[int] = mapped_column(Integer, default=0)
    total_clusters: Mapped[int] = mapped_column(Integer, default=0)
    highest_impact_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
