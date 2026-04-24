"""Pydantic models for Phase 5 scale command center."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class ScaleRecommendationResponse(BaseModel):
    id: uuid.UUID
    recommendation_key: str
    recommended_action: str
    creator_account_id: Optional[uuid.UUID] = None
    incremental_profit_new_account: float = 0.0
    incremental_profit_existing_push: float = 0.0
    comparison_ratio: float = 0.0
    scale_readiness_score: float = 0.0
    cannibalization_risk_score: float = 0.0
    audience_segment_separation: float = 0.0
    expansion_confidence: float = 0.0
    recommended_account_count: int = 2
    best_next_account: Optional[dict] = None
    weekly_action_plan: Optional[dict] = None
    score_components: Optional[dict[str, Any]] = None
    penalties: Optional[dict[str, Any]] = None
    confidence: str = "medium"
    explanation: Optional[str] = None
    is_actioned: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("recommended_action", mode="before")
    @classmethod
    def _coerce_action(cls, v: Any) -> str:
        return v.value if hasattr(v, "value") else str(v)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v: Any) -> str:
        return v.value if hasattr(v, "value") else str(v)


class PortfolioAllocationResponse(BaseModel):
    id: uuid.UUID
    portfolio_id: uuid.UUID
    creator_account_id: uuid.UUID
    brand_id: uuid.UUID
    allocation_pct: float
    budget_allocated: float = 0.0
    posting_capacity_allocated: int
    expected_roi: float
    actual_roi: float
    rationale: Optional[str] = None
    confidence: str
    is_active: bool

    model_config = {"from_attributes": True}

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_p_alloc_conf(cls, v: Any) -> str:
        return v.value if hasattr(v, "value") else str(v)


class ScaleCommandCenterResponse(BaseModel):
    brand_id: str
    brand_name: str
    portfolio_overview: dict[str, Any]
    ai_recommendations: list[dict[str, Any]]
    best_next_account: dict[str, Any] = Field(default_factory=dict)
    recommended_account_count: int = 2
    incremental_tradeoff: dict[str, Any] = Field(default_factory=dict)
    audit: dict[str, Any] = Field(default_factory=dict)
    platform_allocation: dict[str, Any] = Field(default_factory=dict)
    niche_expansion: dict[str, Any] = Field(default_factory=dict)
    revenue_leak_alerts: list[dict[str, Any]] = Field(default_factory=list)
    growth_blockers: list[dict[str, Any]] = Field(default_factory=list)
    saturation_cannibalization_warnings: list[dict[str, Any]] = Field(default_factory=list)
    weekly_action_plan: list[dict[str, Any]] = Field(default_factory=list)
    computed_at: Optional[str] = None
