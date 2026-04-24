"""Unit tests for Operator Copilot engine."""

from packages.scoring.copilot_engine import (
    QUICK_PROMPTS,
    TRUTH_LEVELS,
    build_missing_items,
    build_operator_actions,
    build_provider_readiness,
    build_provider_summary,
    build_quick_status,
    generate_grounded_response,
)

_EMPTY_STATUS = build_quick_status([], [], [], [])
_MISSING = build_missing_items()
_PROVIDERS = build_provider_summary()

URGENCY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def test_quick_prompts_not_empty():
    assert len(QUICK_PROMPTS) >= 10


def test_truth_levels_complete():
    assert "live" in TRUTH_LEVELS
    assert "blocked" in TRUTH_LEVELS


def test_build_quick_status_no_issues():
    out = build_quick_status([], [], [], [])
    assert out["blocked_count"] == 0
    assert out["urgency"] == "normal"


def test_build_quick_status_with_blockers():
    blockers = [{"title": f"b{i}", "description": f"d{i}"} for i in range(5)]
    out = build_quick_status(blockers, [], [], [])
    assert out["blocked_count"] == 5
    assert out["urgency"] != "normal"


def test_build_operator_actions_empty():
    assert (
        build_operator_actions(
            [],
            [],
            [],
            [],
            [],
            [],
            [],
        )
        == []
    )


def test_build_operator_actions_with_scale_alert():
    actions = build_operator_actions(
        [{"alert_type": "test", "description": "test alert"}],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    assert len(actions) >= 1
    assert any(a["action_type"] == "scale_alert" for a in actions)


def test_build_operator_actions_with_growth_approval():
    actions = build_operator_actions(
        [],
        [{"status": "pending_approval", "command_type": "scale", "explanation": "test"}],
        [],
        [],
        [],
        [],
        [],
    )
    assert any(a["action_type"] == "growth_approval" for a in actions)


def test_build_operator_actions_sorted_by_urgency():
    actions = build_operator_actions(
        [],
        [],
        [],
        [{"severity": "low", "avenue_type": "x", "blocker_type": "y", "description": "z"}],
        [],
        [],
        [{"escalation_type": "e", "description": "crit"}],
    )
    assert len(actions) >= 2
    first = URGENCY_ORDER.get(actions[0]["urgency"], 99)
    last = URGENCY_ORDER.get(actions[-1]["urgency"], 99)
    assert first < last


def test_build_missing_items_returns_list():
    items = build_missing_items()
    assert isinstance(items, list)


def test_build_provider_summary_returns_all():
    assert len(build_provider_summary()) >= 20


def test_build_provider_readiness_has_fields():
    for row in build_provider_readiness():
        assert "provider_key" in row
        assert "is_ready" in row
        assert "missing_keys" in row


def test_generate_response_blocked_query():
    out = generate_grounded_response(
        "what is blocked",
        _EMPTY_STATUS,
        [],
        [],
        _PROVIDERS,
    )
    text = out["content"].lower()
    assert "blocker" in text or "blocked" in text or "no active" in text


def test_generate_response_credentials_query():
    missing = [m for m in _MISSING if "credential" in m.get("category", "")]
    if not missing:
        missing = [
            {
                "item": "Test Provider",
                "category": "partial_missing_credentials",
                "description": "needs keys",
                "truth_level": "configured_missing_credentials",
                "action": "Set FOO_KEY",
            }
        ]
    out = generate_grounded_response(
        "what credentials are missing",
        _EMPTY_STATUS,
        [],
        missing,
        _PROVIDERS,
    )
    text = out["content"].lower()
    assert "credential" in text or "missing" in text


def test_generate_response_providers_query():
    out = generate_grounded_response(
        "which providers are active",
        _EMPTY_STATUS,
        [],
        _MISSING,
        _PROVIDERS,
    )
    text = out["content"].lower()
    assert "provider" in text or "live" in text


def test_generate_response_has_truth_boundaries():
    queries = [
        "what is blocked",
        "what credentials are missing",
        "which providers are active",
        "hello",
    ]
    for q in queries:
        out = generate_grounded_response(q, _EMPTY_STATUS, [], _MISSING, _PROVIDERS)
        tb = out["truth_boundaries"]
        assert isinstance(tb, dict)
        assert "status" in tb


def test_generate_response_has_confidence():
    for q in ("what is blocked", "kill something", "unknown query xyz"):
        out = generate_grounded_response(q, _EMPTY_STATUS, [], _MISSING, _PROVIDERS)
        assert isinstance(out["confidence"], float)
        assert out["confidence"] > 0
