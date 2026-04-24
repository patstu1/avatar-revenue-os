"""Generic CRUD service for any SQLAlchemy model. Service-layer pattern."""

from __future__ import annotations

import math
import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class CRUDService(Generic[ModelT]):
    def __init__(self, model: type[ModelT]):
        self.model = model

    async def create(self, db: AsyncSession, **kwargs: Any) -> ModelT:
        instance = self.model(**kwargs)
        db.add(instance)
        await db.flush()
        await db.refresh(instance)
        return instance

    async def get(self, db: AsyncSession, id: uuid.UUID) -> ModelT | None:
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_or_404(self, db: AsyncSession, id: uuid.UUID) -> ModelT:
        instance = await self.get(db, id)
        if instance is None:
            raise ValueError(f"{self.model.__name__} {id} not found")
        return instance

    async def list(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 50,
        filters: dict[str, Any] | None = None,
        order_by: str = "created_at",
        descending: bool = True,
    ) -> dict:
        query = select(self.model)
        count_query = select(func.count()).select_from(self.model)

        if filters:
            for key, value in filters.items():
                col = getattr(self.model, key, None)
                if col is not None and value is not None:
                    query = query.where(col == value)
                    count_query = count_query.where(col == value)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        order_col = getattr(self.model, order_by, self.model.created_at)
        if descending:
            query = query.order_by(order_col.desc())
        else:
            query = query.order_by(order_col.asc())

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        items = list(result.scalars().all())

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, math.ceil(total / page_size)),
        }

    async def update(self, db: AsyncSession, id: uuid.UUID, **kwargs: Any) -> ModelT:
        instance = await self.get_or_404(db, id)
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        await db.flush()
        await db.refresh(instance)
        return instance

    async def delete(self, db: AsyncSession, id: uuid.UUID) -> bool:
        instance = await self.get(db, id)
        if instance is None:
            return False
        await db.delete(instance)
        await db.flush()
        return True
