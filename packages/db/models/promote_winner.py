"""Experiment / Promote-Winner Engine — active testing + promotion system."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class ActiveExperiment(Base):
    __tablename__ = "pw_active_experiments"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    experiment_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    tested_variable: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    target_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    target_offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True)
    target_niche: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    primary_metric: Mapped[str] = mapped_column(String(60), nullable=False)
    secondary_metrics: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    min_sample_size: Mapped[int] = mapped_column(Integer, default=30)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.90)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    config_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)


class PWExperimentVariant(Base):
    __tablename__ = "pw_experiment_variants"

    experiment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pw_active_experiments.id"), nullable=False, index=True)
    variant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_control: Mapped[bool] = mapped_column(Boolean, default=False)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    primary_metric_value: Mapped[float] = mapped_column(Float, default=0.0)
    secondary_metric_values: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PWExperimentAssignment(Base):
    __tablename__ = "pw_experiment_assignments"

    experiment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pw_active_experiments.id"), nullable=False, index=True)
    variant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pw_experiment_variants.id"), nullable=False, index=True)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True)
    assignment_key: Mapped[str] = mapped_column(String(255), nullable=False)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class PWExperimentObservation(Base):
    __tablename__ = "pw_experiment_observations"

    experiment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pw_active_experiments.id"), nullable=False, index=True)
    variant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pw_experiment_variants.id"), nullable=False, index=True)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True)
    metric_name: Mapped[str] = mapped_column(String(60), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, default=0.0)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)


class PWExperimentWinner(Base):
    __tablename__ = "pw_experiment_winners"

    experiment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pw_active_experiments.id"), nullable=False, index=True)
    variant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pw_experiment_variants.id"), nullable=False, index=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    win_margin: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    promoted: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PWExperimentLoser(Base):
    __tablename__ = "pw_experiment_losers"

    experiment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pw_active_experiments.id"), nullable=False, index=True)
    variant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pw_experiment_variants.id"), nullable=False, index=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    loss_margin: Mapped[float] = mapped_column(Float, default=0.0)
    suppressed: Mapped[bool] = mapped_column(Boolean, default=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PromotedWinnerRule(Base):
    __tablename__ = "promoted_winner_rules"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    experiment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pw_active_experiments.id"), nullable=False, index=True)
    winner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pw_experiment_winners.id"), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    rule_key: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_value: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    target_platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    weight_boost: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
