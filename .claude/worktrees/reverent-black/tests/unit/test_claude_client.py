"""Unit tests for Claude copilot client."""
import pytest

from packages.clients.claude_client import (
    ClaudeCopilotClient,
    SYSTEM_PROMPT,
    _build_context_block,
    _hash_context,
)
from packages.scoring.copilot_engine import (
    build_missing_items,
    build_operator_actions,
    build_provider_summary,
    build_quick_status,
    generate_grounded_response,
)

_EMPTY_STATUS = build_quick_status([], [], [], [])
_MISSING = build_missing_items()
_PROVIDERS = build_provider_summary()
_ACTIONS = build_operator_actions([], [], [], [], [], [], [])


def test_client_not_configured_by_default():
    c = ClaudeCopilotClient()
    assert not c.is_configured()


def test_client_configured_with_key():
    c = ClaudeCopilotClient(api_key="sk-ant-test")
    assert c.is_configured()


def test_system_prompt_contains_grounding_rules():
    assert "ONLY answer from the SYSTEM CONTEXT" in SYSTEM_PROMPT
    assert "Do NOT invent" in SYSTEM_PROMPT
    assert "truth boundaries" in SYSTEM_PROMPT.lower() or "LIVE" in SYSTEM_PROMPT


def test_system_prompt_contains_response_modes():
    for mode in ("GROUNDED_ANSWER", "INSUFFICIENT_CONTEXT", "BLOCKED_BY_MISSING_CREDENTIALS",
                  "RECOMMENDATION_ONLY", "OPERATOR_ACTION_SUMMARY"):
        assert mode in SYSTEM_PROMPT


def test_context_block_includes_quick_status():
    block = _build_context_block(_EMPTY_STATUS, [], [], [])
    assert "QUICK STATUS" in block


def test_context_block_includes_provider_stack():
    block = _build_context_block(_EMPTY_STATUS, [], [], _PROVIDERS)
    assert "PROVIDER STACK" in block
    assert "Live:" in block


def test_context_block_includes_actions():
    actions = [{"urgency": "high", "title": "Test blocker", "source_module": "test", "description": "desc"}]
    block = _build_context_block(_EMPTY_STATUS, actions, [], [])
    assert "OPERATOR ACTIONS" in block
    assert "Test blocker" in block


def test_context_block_includes_missing_items():
    items = [{"item": "Claude", "truth_level": "planned", "description": "Not wired", "action": "Set key"}]
    block = _build_context_block(_EMPTY_STATUS, [], items, [])
    assert "MISSING" in block
    assert "Claude" in block


def test_hash_context_deterministic():
    ctx = {"a": 1, "b": [2, 3]}
    h1 = _hash_context(ctx)
    h2 = _hash_context(ctx)
    assert h1 == h2
    assert len(h1) == 16


def test_hash_context_changes_with_data():
    h1 = _hash_context({"a": 1})
    h2 = _hash_context({"a": 2})
    assert h1 != h2


@pytest.mark.asyncio
async def test_missing_key_returns_fallback():
    c = ClaudeCopilotClient(api_key="")
    result = await c.generate_response("test", _EMPTY_STATUS, _ACTIONS, _MISSING, _PROVIDERS)
    assert result["generation_mode"] == "fallback_rule_based"
    assert result["failure_reason"] is not None
    assert "ANTHROPIC_API_KEY" in result["failure_reason"]
    assert result["content"] is None
    assert result["context_hash"]


@pytest.mark.asyncio
async def test_missing_key_preserves_context_hash():
    c = ClaudeCopilotClient(api_key="")
    r1 = await c.generate_response("q1", _EMPTY_STATUS, _ACTIONS, _MISSING, _PROVIDERS)
    r2 = await c.generate_response("q2", _EMPTY_STATUS, _ACTIONS, _MISSING, _PROVIDERS)
    assert r1["context_hash"] == r2["context_hash"]


def test_fallback_rule_based_still_works():
    result = generate_grounded_response("what is blocked", _EMPTY_STATUS, _ACTIONS, _MISSING, _PROVIDERS)
    assert result["content"]
    assert result["truth_boundaries"]


def test_fallback_response_has_truth_boundaries():
    result = generate_grounded_response("what credentials are missing", _EMPTY_STATUS, _ACTIONS, _MISSING, _PROVIDERS)
    assert "status" in result["truth_boundaries"]


def test_fallback_response_has_confidence():
    result = generate_grounded_response("what is blocked", _EMPTY_STATUS, _ACTIONS, _MISSING, _PROVIDERS)
    assert result["confidence"] > 0
