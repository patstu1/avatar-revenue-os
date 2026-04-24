"""Revenue Assignment — maps monetization targets to distribution channels.

Each assignment links an offer (affiliate, sponsor, product) to specific
creator accounts/platforms for targeted revenue routing at publish time.
"""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class RevenueAssignment(Base):
    __tablename__ = "revenue_assignments"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("offers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    creator_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("creator_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="NULL = assign to all accounts for this brand. Set = specific account only.",
    )
    platform: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="NULL = all platforms. Set = restrict this assignment to one platform.",
    )
    weight_override: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Override the offer's default rotation_weight for this specific assignment.",
    )
    cta_override: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Override CTA text for this specific account/platform combination.",
    )
    tracking_params: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        comment="Extra UTM or tracking params to append for this assignment.",
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Higher priority assignments are preferred when multiple match.",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
