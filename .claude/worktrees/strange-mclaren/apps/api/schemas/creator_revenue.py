"""Pydantic schemas for Creator Revenue Avenues Phase A."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class CreatorRevenueOpportunityOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    avenue_type: str
    subtype: str
    target_segment: str
    recommended_package: Optional[str] = None
    expected_value: float
    expected_margin: float
    priority_score: float
    confidence: float
    status: str
    explanation: Optional[str] = None
    details_json: Optional[Any] = None
    created_at: datetime
    class Config:
        from_attributes = True


class UgcServiceActionOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    opportunity_id: Optional[uuid.UUID] = None
    service_type: str
    target_segment: str
    recommended_package: str
    price_band: str
    expected_value: float
    expected_margin: float
    execution_steps_json: Optional[Any] = None
    status: str
    confidence: float
    explanation: Optional[str] = None
    blockers_json: Optional[Any] = None
    created_at: datetime
    class Config:
        from_attributes = True


class ServiceConsultingActionOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    opportunity_id: Optional[uuid.UUID] = None
    service_type: str
    service_tier: str
    target_buyer: str
    price_band: str
    expected_deal_value: float
    execution_plan_json: Optional[Any] = None
    status: str
    confidence: float
    explanation: Optional[str] = None
    blockers_json: Optional[Any] = None
    created_at: datetime
    class Config:
        from_attributes = True


class PremiumAccessActionOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    opportunity_id: Optional[uuid.UUID] = None
    offer_type: str
    target_segment: str
    entry_criteria: Optional[str] = None
    revenue_model: str
    expected_value: float
    execution_plan_json: Optional[Any] = None
    status: str
    confidence: float
    explanation: Optional[str] = None
    blockers_json: Optional[Any] = None
    created_at: datetime
    class Config:
        from_attributes = True


class CreatorRevenueBlockerOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    avenue_type: str
    blocker_type: str
    severity: str
    description: str
    operator_action_needed: str
    resolved: bool
    created_at: datetime
    class Config:
        from_attributes = True


class CreatorRevenueEventOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    opportunity_id: Optional[uuid.UUID] = None
    avenue_type: str
    event_type: str
    revenue: float
    cost: float
    profit: float
    client_name: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True


class LicensingActionOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    opportunity_id: Optional[uuid.UUID] = None
    asset_type: str
    licensing_tier: str
    target_buyer_type: str
    usage_scope: str
    price_band: str
    expected_deal_value: float
    execution_plan_json: Optional[Any] = None
    status: str
    confidence: float
    explanation: Optional[str] = None
    blockers_json: Optional[Any] = None
    created_at: datetime
    class Config:
        from_attributes = True


class SyndicationActionOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    opportunity_id: Optional[uuid.UUID] = None
    syndication_format: str
    target_partner: str
    revenue_model: str
    price_band: str
    expected_value: float
    execution_plan_json: Optional[Any] = None
    status: str
    confidence: float
    explanation: Optional[str] = None
    blockers_json: Optional[Any] = None
    created_at: datetime
    class Config:
        from_attributes = True


class DataProductActionOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    opportunity_id: Optional[uuid.UUID] = None
    product_type: str
    target_segment: str
    revenue_model: str
    price_band: str
    expected_value: float
    execution_plan_json: Optional[Any] = None
    status: str
    confidence: float
    explanation: Optional[str] = None
    blockers_json: Optional[Any] = None
    created_at: datetime
    class Config:
        from_attributes = True


class MerchActionOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    opportunity_id: Optional[uuid.UUID] = None
    product_class: str
    target_segment: str
    price_band: str
    expected_value: float
    execution_plan_json: Optional[Any] = None
    truth_label: str
    status: str
    confidence: float
    explanation: Optional[str] = None
    blockers_json: Optional[Any] = None
    created_at: datetime
    class Config:
        from_attributes = True


class LiveEventActionOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    opportunity_id: Optional[uuid.UUID] = None
    event_type: str
    audience_segment: str
    ticket_model: str
    price_band: str
    expected_value: float
    execution_plan_json: Optional[Any] = None
    truth_label: str
    status: str
    confidence: float
    explanation: Optional[str] = None
    blockers_json: Optional[Any] = None
    created_at: datetime
    class Config:
        from_attributes = True


class OwnedAffiliateProgramActionOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    opportunity_id: Optional[uuid.UUID] = None
    program_type: str
    target_partner_type: str
    incentive_model: str
    partner_tier: str
    expected_value: float
    execution_plan_json: Optional[Any] = None
    truth_label: str
    status: str
    confidence: float
    explanation: Optional[str] = None
    blockers_json: Optional[Any] = None
    created_at: datetime
    class Config:
        from_attributes = True


class AvenueExecutionTruthOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    avenue_type: str
    truth_state: str
    total_actions: int
    active_actions: int
    blocked_actions: int
    total_expected_value: float
    avg_confidence: float
    blocker_count: int
    revenue_to_date: float
    operator_next_action: Optional[str] = None
    missing_integrations: Optional[Any] = None
    details_json: Optional[Any] = None
    created_at: datetime
    class Config:
        from_attributes = True


class HubEntryOut(BaseModel):
    avenue_type: str
    avenue_display_name: str
    truth_state: str
    total_actions: int
    active_actions: int
    blocked_actions: int
    total_expected_value: float
    avg_confidence: float
    blocker_count: int
    revenue_to_date: float
    hub_score: float
    operator_next_action: Optional[str] = None
    missing_integrations: list[str] = []
    top_blockers: list[str] = []


class HubSummaryOut(BaseModel):
    entries: list[HubEntryOut]
    total_expected_value: float
    total_revenue_to_date: float
    total_blockers: int
    avenues_live: int
    avenues_blocked: int
    avenues_executing: int
    avenues_queued: int
    avenues_recommended: int
    event_rollup: Optional[Any] = None


class RecomputeSummaryOut(BaseModel):
    created: int = 0
    updated: int = 0
    details: Optional[str] = None
