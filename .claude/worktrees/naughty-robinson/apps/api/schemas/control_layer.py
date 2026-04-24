"""Schemas for the Control Layer — the operator's primary command surface."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SystemHealthResponse(BaseModel):
    """Real-time system health for the control layer."""
    # Entity counts
    total_brands: int = 0
    total_accounts: int = 0
    total_offers: int = 0
    total_content_items: int = 0

    # Content pipeline state
    content_draft: int = 0
    content_generating: int = 0
    content_review: int = 0
    content_approved: int = 0
    content_publishing: int = 0
    content_published: int = 0
    content_failed: int = 0

    # Job state
    jobs_pending: int = 0
    jobs_running: int = 0
    jobs_completed_24h: int = 0
    jobs_failed_24h: int = 0
    jobs_retrying: int = 0

    # Actions
    actions_pending: int = 0
    actions_critical: int = 0
    actions_completed_24h: int = 0

    # Blockers & alerts
    active_blockers: int = 0
    active_alerts: int = 0

    # Revenue
    total_revenue_30d: float = 0.0
    total_cost_30d: float = 0.0

    # Providers
    providers_healthy: int = 0
    providers_degraded: int = 0
    providers_down: int = 0

    # Timestamp
    snapshot_at: Optional[datetime] = None


class OperatorActionResponse(BaseModel):
    id: str
    action_type: str
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    category: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    brand_id: Optional[str] = None
    source_module: Optional[str] = None
    status: str = "pending"
    action_payload: dict = {}
    result: dict = {}
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    expires_at: Optional[datetime] = None


class OperatorActionList(BaseModel):
    actions: list[OperatorActionResponse] = []
    total: int = 0
    pending_count: int = 0
    critical_count: int = 0


class SystemEventResponse(BaseModel):
    id: str
    event_domain: str
    event_type: str
    event_severity: str = "info"
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    actor_type: str = "system"
    summary: str
    details: dict = {}
    requires_action: bool = False
    action_taken: bool = False
    created_at: Optional[datetime] = None


class SystemEventList(BaseModel):
    events: list[SystemEventResponse] = []
    total: int = 0


class ControlLayerDashboard(BaseModel):
    """The complete control layer response — everything the operator needs."""
    health: SystemHealthResponse
    pending_actions: list[OperatorActionResponse] = []
    recent_events: list[SystemEventResponse] = []
    critical_count: int = 0
    pending_action_count: int = 0
    failed_jobs_24h: int = 0


class ActionCompleteRequest(BaseModel):
    result: dict = {}


class ActionDismissRequest(BaseModel):
    reason: Optional[str] = None
