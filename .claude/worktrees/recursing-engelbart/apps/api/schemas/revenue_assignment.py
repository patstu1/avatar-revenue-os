"""Revenue assignment schemas."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RevenueAssignmentCreate(BaseModel):
    brand_id: uuid.UUID
    assignment_type: str = Field(..., pattern=r"^(offer|affiliate|newsletter|b2b)$")
    target_id: uuid.UUID
    target_name: Optional[str] = None
    account_id: Optional[uuid.UUID] = None
    platform: Optional[str] = None
    priority: int = 0
    is_active: bool = True
    config: dict = Field(default_factory=dict)


class RevenueAssignmentUpdate(BaseModel):
    target_name: Optional[str] = None
    account_id: Optional[uuid.UUID] = None
    platform: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    config: Optional[dict] = None


class RevenueAssignmentResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    assignment_type: str
    target_id: uuid.UUID
    target_name: Optional[str] = None
    account_id: Optional[uuid.UUID] = None
    platform: Optional[str] = None
    priority: int
    is_active: bool
    config: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
