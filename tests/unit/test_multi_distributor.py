"""Unit tests — multi-distributor publishing layer: clients, router, failover."""
from __future__ import annotations
import os
import pytest
import asyncio


# ── Publer Client ──

def test_publer_blocked_without_key():
    from packages.clients.publer_client import PublerClient
    c = PublerClient()
    assert not c._is_configured()
    result = asyncio.run(c.get_profiles())
    assert not result["success"]
    assert "PUBLER_API_KEY" in result["error"]


def test_publer_create_post_blocked():
    from packages.clients.publer_client import PublerClient
    c = PublerClient()
    result = asyncio.run(c.create_post(["acct1"], "Hello world"))
    assert not result["success"]
    assert result.get("blocked")


def test_publer_get_post_blocked():
    from packages.clients.publer_client import PublerClient
    c = PublerClient()
    result = asyncio.run(c.get_post("fake-id"))
    assert not result["success"]


# ── Ayrshare Client ──

def test_ayrshare_blocked_without_key():
    from packages.clients.ayrshare_client import AyrshareClient
    c = AyrshareClient()
    assert not c._is_configured()
    result = asyncio.run(c.get_profiles())
    assert not result["success"]
    assert "AYRSHARE_API_KEY" in result["error"]


def test_ayrshare_create_post_blocked():
    from packages.clients.ayrshare_client import AyrshareClient
    c = AyrshareClient()
    result = asyncio.run(c.create_post(["twitter"], "Hello world"))
    assert not result["success"]
    assert result.get("blocked")


def test_ayrshare_get_post_blocked():
    from packages.clients.ayrshare_client import AyrshareClient
    c = AyrshareClient()
    result = asyncio.run(c.get_post("fake-id"))
    assert not result["success"]


def test_ayrshare_analytics_blocked():
    from packages.clients.ayrshare_client import AyrshareClient
    c = AyrshareClient()
    result = asyncio.run(c.get_analytics("fake-id", ["twitter"]))
    assert not result["success"]


# ── Distributor Router ──

def test_router_no_distributors_configured():
    from packages.clients.distributor_router import get_configured_distributors
    old_buffer = os.environ.pop("BUFFER_API_KEY", None)
    old_publer = os.environ.pop("PUBLER_API_KEY", None)
    old_ayrshare = os.environ.pop("AYRSHARE_API_KEY", None)
    try:
        configured = get_configured_distributors()
        assert len(configured) == 0
    finally:
        if old_buffer: os.environ["BUFFER_API_KEY"] = old_buffer
        if old_publer: os.environ["PUBLER_API_KEY"] = old_publer
        if old_ayrshare: os.environ["AYRSHARE_API_KEY"] = old_ayrshare


def test_router_detects_configured_distributors():
    from packages.clients.distributor_router import get_configured_distributors
    old = os.environ.get("PUBLER_API_KEY")
    os.environ["PUBLER_API_KEY"] = "test-key-123"
    try:
        configured = get_configured_distributors()
        names = [a.name for a in configured]
        assert "publer" in names
    finally:
        if old:
            os.environ["PUBLER_API_KEY"] = old
        else:
            del os.environ["PUBLER_API_KEY"]


def test_router_any_distributor_check():
    from packages.clients.distributor_router import any_distributor_configured
    old = os.environ.get("AYRSHARE_API_KEY")
    os.environ["AYRSHARE_API_KEY"] = "test-key"
    try:
        assert any_distributor_configured()
    finally:
        if old:
            os.environ["AYRSHARE_API_KEY"] = old
        else:
            del os.environ["AYRSHARE_API_KEY"]


def test_router_publish_request_dataclass():
    from packages.clients.distributor_router import PublishRequest
    req = PublishRequest(text="Hello", platform="youtube", profile_ids=["p1"])
    assert req.text == "Hello"
    assert req.platform == "youtube"
    assert req.profile_ids == ["p1"]
    assert req.media_urls is None


def test_router_publish_result_dataclass():
    from packages.clients.distributor_router import PublishResult
    res = PublishResult(success=True, distributor="buffer", post_id="123")
    assert res.success
    assert res.distributor == "buffer"
    assert not res.failover_attempted


def test_router_failover_all_unconfigured():
    from packages.clients.distributor_router import publish_with_failover, PublishRequest
    old_buffer = os.environ.pop("BUFFER_API_KEY", None)
    old_publer = os.environ.pop("PUBLER_API_KEY", None)
    old_ayrshare = os.environ.pop("AYRSHARE_API_KEY", None)
    try:
        req = PublishRequest(text="Test", platform="youtube")
        result = asyncio.run(publish_with_failover(req))
        assert not result.success
        assert "No distribution service configured" in result.error
    finally:
        if old_buffer: os.environ["BUFFER_API_KEY"] = old_buffer
        if old_publer: os.environ["PUBLER_API_KEY"] = old_publer
        if old_ayrshare: os.environ["AYRSHARE_API_KEY"] = old_ayrshare


def test_router_get_distributor_status():
    from packages.clients.distributor_router import get_distributor_status
    status = get_distributor_status()
    assert "configured" in status
    assert "all_distributors" in status
    assert len(status["all_distributors"]) == 3
    names = [d["name"] for d in status["all_distributors"]]
    assert "buffer" in names
    assert "publer" in names
    assert "ayrshare" in names


def test_router_platform_support():
    from packages.clients.distributor_router import BufferAdapter, PubierAdapter, AyrshareAdapter
    buffer = BufferAdapter()
    assert buffer.supports_platform("youtube")
    assert not buffer.supports_platform("reddit")
    assert not buffer.supports_platform("pinterest")

    publer = PubierAdapter()
    assert publer.supports_platform("reddit")
    assert publer.supports_platform("pinterest")

    ayrshare = AyrshareAdapter()
    assert ayrshare.supports_platform("reddit")


def test_router_platform_filtering():
    from packages.clients.distributor_router import get_available_for_platform, _ADAPTER_REGISTRY
    old_buffer = os.environ.get("BUFFER_API_KEY")
    old_publer = os.environ.get("PUBLER_API_KEY")
    os.environ["BUFFER_API_KEY"] = "test"
    os.environ["PUBLER_API_KEY"] = "test"
    try:
        reddit_adapters = get_available_for_platform("reddit")
        names = [a.name for a in reddit_adapters]
        assert "buffer" not in names
        assert "publer" in names
    finally:
        if old_buffer:
            os.environ["BUFFER_API_KEY"] = old_buffer
        else:
            del os.environ["BUFFER_API_KEY"]
        if old_publer:
            os.environ["PUBLER_API_KEY"] = old_publer
        else:
            del os.environ["PUBLER_API_KEY"]


def test_ayrshare_platform_mapping():
    from packages.clients.distributor_router import PLATFORM_MAP_AYRSHARE
    assert PLATFORM_MAP_AYRSHARE["x"] == "twitter"
    assert PLATFORM_MAP_AYRSHARE["youtube"] == "youtube"
    assert PLATFORM_MAP_AYRSHARE["reddit"] == "reddit"


# ── Readiness Engine ──

def test_readiness_accepts_any_distributor():
    from packages.scoring.autonomous_readiness_engine import evaluate_autonomous_readiness
    old_buffer = os.environ.pop("BUFFER_API_KEY", None)
    old_publer = os.environ.pop("PUBLER_API_KEY", None)
    os.environ["AYRSHARE_API_KEY"] = "test-key"
    os.environ["ANTHROPIC_API_KEY"] = "test"
    os.environ["GOOGLE_AI_API_KEY"] = "test"
    os.environ["DEEPSEEK_API_KEY"] = "test"
    try:
        result = evaluate_autonomous_readiness()
        cond1 = next(c for c in result["conditions"] if c["id"] == 1)
        cond3 = next(c for c in result["conditions"] if c["id"] == 3)
        assert cond1["passed"]
        assert cond3["passed"]
    finally:
        del os.environ["AYRSHARE_API_KEY"]
        del os.environ["ANTHROPIC_API_KEY"]
        del os.environ["GOOGLE_AI_API_KEY"]
        del os.environ["DEEPSEEK_API_KEY"]
        if old_buffer: os.environ["BUFFER_API_KEY"] = old_buffer
        if old_publer: os.environ["PUBLER_API_KEY"] = old_publer
