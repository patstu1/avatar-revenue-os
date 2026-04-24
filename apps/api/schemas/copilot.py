"""Pydantic schemas for Operator Copilot APIs."""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CopilotSessionCreate(BaseModel):
    title: str = Field(default="Operator session", max_length=255)


class CopilotSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: str
    message_count: int
    last_message_at: str | None = None


class CopilotMessageCreate(BaseModel):
    content: str
    quick_prompt_key: str | None = None


class CopilotMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    grounding_sources: list[Any] | None = None
    truth_boundaries: dict[str, Any] | None = None
    quick_prompt_key: str | None = None
    confidence: float | None = None
    generation_mode: str | None = None
    generation_model: str | None = None
    context_hash: str | None = None
    failure_reason: str | None = None


class CopilotPostMessagesResponse(BaseModel):
    messages: list[CopilotMessageOut]
