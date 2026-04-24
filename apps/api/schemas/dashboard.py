"""Schemas for dashboard overview API."""

from pydantic import BaseModel


class DashboardOverview(BaseModel):
    total_brands: int = 0
    total_avatars: int = 0
    total_offers: int = 0
    total_creator_accounts: int = 0
    total_content_items: int = 0
    total_publish_jobs: int = 0
    total_audit_entries: int = 0
    total_system_jobs: int = 0
    total_provider_cost: float = 0.0
    active_accounts_by_platform: dict = {}
    recent_audit_actions: list = []
    recent_jobs: list = []
