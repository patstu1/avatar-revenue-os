"""Audit logging service — persists every critical action."""

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.system import AuditLog


async def log_action(
    db: AsyncSession,
    action: str,
    *,
    organization_id: Optional[uuid.UUID] = None,
    brand_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    actor_type: str = "system",
    entity_type: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    entry = AuditLog(
        organization_id=organization_id,
        brand_id=brand_id,
        user_id=user_id,
        actor_type=actor_type,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    return entry
