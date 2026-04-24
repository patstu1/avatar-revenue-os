"""Schemas for system jobs and audit logs."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SystemJobResponse(BaseModel):
    id: uuid.UUID
    brand_id: Optional[uuid.UUID]
    job_name: str
    job_type: str
    queue: str
    status: str
    celery_task_id: Optional[str]
    error_message: Optional[str]
    retries: int
    max_retries: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    organization_id: Optional[uuid.UUID]
    brand_id: Optional[uuid.UUID]
    user_id: Optional[uuid.UUID]
    actor_type: str
    action: str
    entity_type: Optional[str]
    entity_id: Optional[uuid.UUID]
    details: Optional[dict]
    ip_address: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    pages: int
