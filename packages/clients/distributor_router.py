"""Unified Distribution Router — multi-distributor publishing with automatic failover.

Tries distributors in priority order: Buffer → Publer → Ayrshare.
If the primary fails, falls back to the next configured distributor.
Tracks success/failure rates to auto-promote the most reliable distributor.

Future-proof: direct platform API adapters can be added as additional distributors.
"""
from __future__ import annotations
import logging
import os
from typing import Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

PLATFORM_MAP_AYRSHARE = {
    "youtube": "youtube", "tiktok": "tiktok", "instagram": "instagram",
    "x": "twitter", "twitter": "twitter", "linkedin": "linkedin",
    "reddit": "reddit", "pinterest": "pinterest", "facebook": "facebook",
}


@dataclass
class PublishRequest:
    """Unified publish request across all distributors."""
    text: str
    platform: str
    profile_ids: list[str] = field(default_factory=list)
    media_urls: Optional[list[str]] = None
    link_url: Optional[str] = None
    scheduled_at: Optional[str] = None


@dataclass
class PublishResult:
    """Unified result from any distributor."""
    success: bool
    distributor: str
    post_id: Optional[str] = None
    error: Optional[str] = None
    raw_response: Optional[dict] = None
    failover_attempted: bool = False
    distributors_tried: list[str] = field(default_factory=list)


class DistributorAdapter:
    """Base interface for all distribution adapters."""
    name: str = "base"

    def is_configured(self) -> bool:
        raise NotImplementedError

    def supports_platform(self, platform: str) -> bool:
        return True

    async def publish(self, request: PublishRequest) -> PublishResult:
        raise NotImplementedError

    async def get_profiles(self) -> dict[str, Any]:
        raise NotImplementedError


class BufferAdapter(DistributorAdapter):
    name = "buffer"

    def is_configured(self) -> bool:
        return bool(os.environ.get("BUFFER_API_KEY"))

    def supports_platform(self, platform: str) -> bool:
        return platform.lower() not in ("reddit", "pinterest")

    async def publish(self, request: PublishRequest) -> PublishResult:
        from packages.clients.external_clients import BufferClient
        client = BufferClient()
        if not client._is_configured():
            return PublishResult(success=False, distributor=self.name, error="BUFFER_API_KEY not configured")

        result = await client.create_update(
            profile_ids=request.profile_ids,
            text=request.text,
            media={"link": request.media_urls[0]} if request.media_urls else None,
            scheduled_at=request.scheduled_at,
        )
        if result.get("success"):
            post_id = result.get("data", {}).get("updates", [{}])[0].get("id", "") if isinstance(result.get("data"), dict) else ""
            return PublishResult(success=True, distributor=self.name, post_id=str(post_id), raw_response=result)
        return PublishResult(success=False, distributor=self.name, error=result.get("error", "Buffer publish failed"), raw_response=result)

    async def get_profiles(self) -> dict[str, Any]:
        from packages.clients.external_clients import BufferClient
        return await BufferClient().get_profiles()


class PublerAdapter(DistributorAdapter):
    name = "publer"

    def is_configured(self) -> bool:
        return bool(os.environ.get("PUBLER_API_KEY"))

    async def publish(self, request: PublishRequest) -> PublishResult:
        from packages.clients.publer_client import PublerClient
        client = PublerClient()
        if not client._is_configured():
            return PublishResult(success=False, distributor=self.name, error="PUBLER_API_KEY not configured")

        account_ids = request.profile_ids or []
        result = await client.create_post(
            account_ids=account_ids,
            text=request.text,
            media_urls=request.media_urls,
            link_url=request.link_url,
            scheduled_at=request.scheduled_at,
        )
        if result.get("success"):
            post_id = result.get("data", {}).get("id", "") if isinstance(result.get("data"), dict) else ""
            return PublishResult(success=True, distributor=self.name, post_id=str(post_id), raw_response=result)
        return PublishResult(success=False, distributor=self.name, error=result.get("error", "Publer publish failed"), raw_response=result)

    async def get_profiles(self) -> dict[str, Any]:
        from packages.clients.publer_client import PublerClient
        return await PublerClient().get_profiles()


class AyrshareAdapter(DistributorAdapter):
    name = "ayrshare"

    def is_configured(self) -> bool:
        return bool(os.environ.get("AYRSHARE_API_KEY"))

    async def publish(self, request: PublishRequest) -> PublishResult:
        from packages.clients.ayrshare_client import AyrshareClient
        client = AyrshareClient()
        if not client._is_configured():
            return PublishResult(success=False, distributor=self.name, error="AYRSHARE_API_KEY not configured")

        platform_key = PLATFORM_MAP_AYRSHARE.get(request.platform.lower(), request.platform.lower())
        result = await client.create_post(
            platforms=[platform_key],
            text=request.text,
            media_urls=request.media_urls,
            link_url=request.link_url,
            scheduled_date=request.scheduled_at,
        )
        if result.get("success"):
            post_id = result.get("data", {}).get("id", "") if isinstance(result.get("data"), dict) else ""
            return PublishResult(success=True, distributor=self.name, post_id=str(post_id), raw_response=result)
        return PublishResult(success=False, distributor=self.name, error=result.get("error", "Ayrshare publish failed"), raw_response=result)

    async def get_profiles(self) -> dict[str, Any]:
        from packages.clients.ayrshare_client import AyrshareClient
        return await AyrshareClient().get_profiles()


_ADAPTER_REGISTRY: list[DistributorAdapter] = [
    BufferAdapter(),
    PublerAdapter(),
    AyrshareAdapter(),
]

_success_count: dict[str, int] = {}
_failure_count: dict[str, int] = {}


def get_configured_distributors() -> list[DistributorAdapter]:
    """Return all distributors that have credentials configured."""
    return [a for a in _ADAPTER_REGISTRY if a.is_configured()]


def get_available_for_platform(platform: str) -> list[DistributorAdapter]:
    """Return configured distributors that support a specific platform."""
    return [a for a in get_configured_distributors() if a.supports_platform(platform)]


def get_priority_order(platform: str) -> list[DistributorAdapter]:
    """Return distributors ordered by reliability score (success rate)."""
    available = get_available_for_platform(platform)
    if not available:
        return []

    def reliability(adapter: DistributorAdapter) -> float:
        s = _success_count.get(adapter.name, 0)
        f = _failure_count.get(adapter.name, 0)
        total = s + f
        if total == 0:
            return 0.5
        return s / total

    return sorted(available, key=reliability, reverse=True)


async def publish_with_failover(request: PublishRequest) -> PublishResult:
    """Publish content, trying distributors in priority order with automatic failover."""
    ordered = get_priority_order(request.platform)
    if not ordered:
        return PublishResult(
            success=False, distributor="none",
            error="No distribution service configured. Set BUFFER_API_KEY, PUBLER_API_KEY, or AYRSHARE_API_KEY.",
        )

    tried: list[str] = []
    last_error = ""

    for adapter in ordered:
        tried.append(adapter.name)
        try:
            result = await adapter.publish(request)
            if result.success:
                _success_count[adapter.name] = _success_count.get(adapter.name, 0) + 1
                result.distributors_tried = tried
                result.failover_attempted = len(tried) > 1
                logger.info("publish.success distributor=%s platform=%s failover=%s", adapter.name, request.platform, result.failover_attempted)
                return result

            _failure_count[adapter.name] = _failure_count.get(adapter.name, 0) + 1
            last_error = result.error or "unknown error"
            logger.warning("publish.failed distributor=%s error=%s, trying next", adapter.name, last_error)
        except Exception as e:
            _failure_count[adapter.name] = _failure_count.get(adapter.name, 0) + 1
            last_error = str(e)
            logger.exception("publish.exception distributor=%s", adapter.name)

    return PublishResult(
        success=False, distributor="none",
        error=f"All distributors failed. Last error: {last_error}",
        distributors_tried=tried, failover_attempted=True,
    )


def any_distributor_configured() -> bool:
    """Check if at least one distribution service has credentials."""
    return len(get_configured_distributors()) > 0


def get_distributor_status() -> dict[str, Any]:
    """Return status of all distributors for readiness checks."""
    return {
        "configured": [a.name for a in get_configured_distributors()],
        "available_count": len(get_configured_distributors()),
        "all_distributors": [
            {
                "name": a.name,
                "configured": a.is_configured(),
                "successes": _success_count.get(a.name, 0),
                "failures": _failure_count.get(a.name, 0),
            }
            for a in _ADAPTER_REGISTRY
        ],
    }
