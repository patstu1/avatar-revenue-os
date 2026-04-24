"""Pydantic schemas for Operator Copilot APIs."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class CopilotSessionCreate(BaseModel):
    title: str = Field(default="Operator session", max_length=255)


class CopilotSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: str
    message_count: int
    last_message_at: Optional[str] = None


class CopilotMessageCreate(BaseModel):
    content: str
    quick_prompt_key: Optional[str] = None


class CopilotMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    grounding_sources: Optional[list[Any]] = None
    truth_boundaries: Optional[dict[str, Any]] = None
    quick_prompt_key: Optional[str] = None
    confidence: Optional[float] = None
    generation_mode: Optional[str] = None
    generation_model: Optional[str] = None
    context_hash: Optional[str] = None
    failure_reason: Optional[str] = None


class CopilotPostMessagesResponse(BaseModel):
    messages: list[CopilotMessageOut]
