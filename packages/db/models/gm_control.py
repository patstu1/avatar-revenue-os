"""GM operating truth (Batch 4) — approvals, escalations, stage tracking.

This is the *operational* GM surface, separate from the conversational
``gm.py`` (GMSession/GMMessage/GMBlueprint). The stage_controller
writes rows here; the GM control-board endpoint reads them.

Canonical ``gm_actions`` semantics layer on top of the existing
``operator_actions`` table — no schema change to that table. This
module only adds new tables: ``gm_approvals``, ``gm_escalations``,
``stage_states``.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base

GM_APPROVAL_STATUSES = [
    "pending",
    "approved",
    "rejected",
    "expired",
    "auto_approved",
]

GM_ESCALATION_STATUSES = ["open", "acknowledged", "resolved", "dismissed"]

# Canonical action classes (semantics for operator_actions rows written by
# the stage_controller). Stored as action_type prefixes / metadata.
GM_ACTION_CLASSES = ["auto_execute", "approval_required", "escalate"]


# ── 1. GMApproval ────────────────────────────────────────────────────────────


class GMApproval(Base):
    """Operator approval queue item: a money-sensitive or high-risk
    action requires a human decision before it executes.
    """

    __tablename__ = "gm_approvals"
    __table_args__ = (
        UniqueConstraint(
            "org_id",
            "entity_type",
            "entity_id",
            "action_type",
            name="uq_gm_approvals_entity_action",
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )

    action_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="medium", nullable=False, index=True)

    proposed_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    decision_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    source_module: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── 2. GMEscalation ──────────────────────────────────────────────────────────


class GMEscalation(Base):
    """Escalation surface: stuck stage, missing data, repeated failure."""

    __tablename__ = "gm_escalations"
    __table_args__ = (
        UniqueConstraint(
            "org_id",
            "entity_type",
            "entity_id",
            "reason_code",
            name="uq_gm_escalations_entity_reason",
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )

    entity_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    reason_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    stage: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="warning", nullable=False, index=True)

    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False, index=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    source_module: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── 3. StageState ────────────────────────────────────────────────────────────


class StageState(Base):
    """Per-entity stage + SLA tracker used by the stage_controller + watcher."""

    __tablename__ = "stage_states"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            name="uq_stage_states_entity",
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    stage: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    previous_stage: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    entered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    last_watcher_tick_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_stuck: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    stuck_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
