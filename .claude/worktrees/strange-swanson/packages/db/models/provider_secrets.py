"""Encrypted provider API key storage — keys entered via dashboard UI."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class ProviderSecret(Base):
    __tablename__ = "provider_secrets"
    __table_args__ = (
        UniqueConstraint("organization_id", "provider_name", name="uq_org_provider"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    last_rotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
