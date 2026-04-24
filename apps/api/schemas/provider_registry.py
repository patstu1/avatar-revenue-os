"""Pydantic schemas for Provider Registry APIs."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProviderEntryOut(BaseModel):
    id: str
    provider_key: str
    display_name: str
    category: str
    provider_type: str
    description: str | None = None
    env_keys: list[str] = Field(default_factory=list)
    credential_status: str = "not_configured"
    integration_status: str = "stubbed"
    is_primary: bool = False
    is_fallback: bool = False
    is_optional: bool = False
    capabilities_json: Any | None = None
    config_json: dict[str, Any] | None = None
    is_active: bool = True
    created_at: str | None = None


class ProviderCapabilityOut(BaseModel):
    id: str
    provider_key: str
    capability: str
    description: str | None = None
    is_active: bool = True


class ProviderDependencyOut(BaseModel):
    id: str
    provider_key: str
    module_path: str
    dependency_type: str = "required"
    description: str | None = None
    is_active: bool = True


class ProviderReadinessOut(BaseModel):
    id: str
    brand_id: str
    provider_key: str
    credential_status: str = "not_configured"
    integration_status: str = "stubbed"
    is_ready: bool = False
    missing_env_keys: list[str] = Field(default_factory=list)
    operator_action: str | None = None
    details_json: dict[str, Any] | None = None
    is_active: bool = True
    created_at: str | None = None


class ProviderUsageEventOut(BaseModel):
    id: str
    brand_id: str | None = None
    provider_key: str
    event_type: str
    success: bool = True
    error_message: str | None = None
    cost: float = 0.0
    details_json: dict[str, Any] | None = None
    created_at: str | None = None


class ProviderBlockerOut(BaseModel):
    id: str
    brand_id: str
    provider_key: str
    blocker_type: str
    severity: str = "high"
    description: str
    operator_action_needed: str
    resolved: bool = False
    is_active: bool = True
    created_at: str | None = None


class AuditSummaryOut(BaseModel):
    status: str = "completed"
    providers_audited: int = 0
    capabilities_written: int = 0
    dependencies_written: int = 0
    readiness_reports_written: int = 0
    blockers_found: int = 0
    detail: str | None = None
