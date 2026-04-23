"""Experiments, variants, winner cloning."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.enums import ExperimentStatus, JobStatus


class Experiment(Base):
    __tablename__ = "experiments"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hypothesis: Mapped[Optional[str]] = mapped_column(Text)
    experiment_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_metric: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[ExperimentStatus] = mapped_column(
        Enum(ExperimentStatus), default=ExperimentStatus.DRAFT, index=True
    )
    min_sample_size: Mapped[int] = mapped_column(Integer, default=100)
    current_sample_size: Mapped[int] = mapped_column(Integer, default=0)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.95)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    winning_variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    results_summary: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    conclusion: Mapped[Optional[str]] = mapped_column(Text)


class ExperimentVariant(Base):
    __tablename__ = "experiment_variants"

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiments.id"), nullable=False, index=True
    )
    variant_label: Mapped[str] = mapped_column(String(100), nullable=False)
    is_control: Mapped[bool] = mapped_column(Boolean, default=False)
    variant_config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id")
    )
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    target_metric_value: Mapped[float] = mapped_column(Float, default=0.0)
    statistical_significance: Mapped[float] = mapped_column(Float, default=0.0)
    is_winner: Mapped[bool] = mapped_column(Boolean, default=False)


class WinnerCloneJob(Base):
    __tablename__ = "winner_clone_jobs"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    source_content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=False
    )
    target_creator_account_ids: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    target_platforms: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    clone_strategy: Mapped[str] = mapped_column(String(100), default="adapt")
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING, index=True)
    cloned_content_ids: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    results: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
