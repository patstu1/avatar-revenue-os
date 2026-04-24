"""Action Deduplication — prevents the system from creating the same action repeatedly.

At mass scale (20+ brands, 4h cycles), the same opportunities are detected
every cycle. Without dedup, the operator drowns in hundreds of identical actions.

This module checks if an equivalent action already exists before creating a new one.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.system_events import OperatorAction


async def action_exists(
    db: AsyncSession,
    org_id: uuid.UUID,
    action_type: str,
    *,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
) -> bool:
    """Check if an equivalent pending action already exists.

    An action is considered duplicate if it has the same:
    - action_type
    - entity_type + entity_id (if provided)
    - brand_id (if provided)
    - status = "pending"
    """
    query = select(OperatorAction.id).where(
        OperatorAction.organization_id == org_id,
        OperatorAction.action_type == action_type,
        OperatorAction.status == "pending",
    )

    if entity_type and entity_id:
        query = query.where(
            OperatorAction.entity_type == entity_type,
            OperatorAction.entity_id == entity_id,
        )

    if brand_id:
        query = query.where(OperatorAction.brand_id == brand_id)

    result = (await db.execute(query.limit(1))).scalar_one_or_none()
    return result is not None
