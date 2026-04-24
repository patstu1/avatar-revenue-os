"""Pydantic models for Phase 7 APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SponsorOpportunitiesResponse(BaseModel):
    packages: list[dict[str, Any]] = Field(default_factory=list)
    profiles: list[dict[str, Any]] = Field(default_factory=list)
    opportunities: list[dict[str, Any]] = Field(default_factory=list)


class CommentCashResponse(BaseModel):
    signals: list[dict[str, Any]] = Field(default_factory=list)


class RoadmapResponse(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)


class CapitalAllocationResponse(BaseModel):
    allocations: list[dict[str, Any]] = Field(default_factory=list)


class KnowledgeGraphResponse(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class OperatorCockpitResponse(BaseModel):
    brand_id: str
    top_roadmap_items: list[dict[str, Any]] = Field(default_factory=list)
    capital_allocation: list[dict[str, Any]] = Field(default_factory=list)
    open_leaks: list[dict[str, Any]] = Field(default_factory=list)
    leak_summary: dict[str, Any] = Field(default_factory=dict)
    scale_action: dict[str, Any] = Field(default_factory=dict)
    growth_blockers: list[dict[str, Any]] = Field(default_factory=list)
    trust_avg: float = 0.0
    sponsor_packages: list[dict[str, Any]] = Field(default_factory=list)
    comment_cash_signals: list[dict[str, Any]] = Field(default_factory=list)
    expansion_targets: list[dict[str, Any]] = Field(default_factory=list)
