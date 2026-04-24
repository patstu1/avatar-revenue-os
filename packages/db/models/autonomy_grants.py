"""Brand Autonomy Grants — per-brand-per-action-type promotion ledger.

A grant allows a specific action type to run autonomously for a specific
brand once the brand has demonstrated sufficient success with that action.

Grants are created and revoked by the hourly `update_autonomy_grants` task,
not by human operators. Operators can manually revoke a grant via the API.

Daily caps prevent runaway execution even for trusted brands.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class BrandAutonomyGrant(Base):
    __tablename__ = "brand_autonomy_grants"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="The action_type this grant applies to (e.g. create_content_for_offer)",
    )

    # --- Grant state ---
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    granted_by: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="auto",
        comment="'auto' (from update_autonomy_grants task) or an operator user_id",
    )
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)

    # --- Daily cap ---
    daily_cap: Mapped[int] = mapped_column(
        Integer,
        default=5,
        comment="Max auto-approvals per UTC day for this (brand, action_type) pair",
    )
    today_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reset_date: Mapped[date] = mapped_column(Date, default=date.today)

    # --- Revocation ---
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint("brand_id", "action_type", name="uq_brand_autonomy_grant_brand_action"),
        Index("ix_brand_autonomy_grants_brand_active", "brand_id", postgresql_where="revoked_at IS NULL"),
    )
