"""Unit tests — autonomous content farm: niche research, warmup, voice, generation, ideation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# ── Niche Research Engine ──


def test_score_niche_basic():
    from packages.scoring.niche_research_engine import NICHE_DATABASE, score_niche

    finance = next(n for n in NICHE_DATABASE if n["niche"] == "personal_finance")
    result = score_niche(finance, "youtube")
    assert result["composite_score"] > 0
    assert result["monetization_score"] > 0
    assert result["niche"] == "personal_finance"
    assert result["platform"] == "youtube"


def test_rank_niches_returns_ordered():
    from packages.scoring.niche_research_engine import rank_niches

    ranked = rank_niches(top_n=5)
    assert len(ranked) == 5
    scores = [r["composite_score"] for r in ranked]
    assert scores == sorted(scores, reverse=True)


def test_recommend_initial_niches_unique():
    from packages.scoring.niche_research_engine import recommend_initial_niches

    recs = recommend_initial_niches(5)
    assert len(recs) == 5
    niches = [r["niche"] for r in recs]
    assert len(set(niches)) == 5


def test_niche_trend_velocity_boost():
    from packages.scoring.niche_research_engine import NICHE_DATABASE, score_niche

    finance = next(n for n in NICHE_DATABASE if n["niche"] == "personal_finance")
    no_trends = score_niche(finance, "youtube", trend_signals=[])
    with_trends = score_niche(
        finance,
        "youtube",
        trend_signals=[
            {"title": "New budgeting app released"},
            {"title": "Investing in 2026"},
            {"title": "How to save money fast"},
            {"title": "Credit score tips"},
        ],
    )
    assert with_trends["trend_velocity"] > no_trends["trend_velocity"]
    assert with_trends["composite_score"] > no_trends["composite_score"]


def test_niche_subreddits():
    from packages.scoring.niche_research_engine import get_niche_subreddits

    subs = get_niche_subreddits("personal_finance")
    assert len(subs) >= 2
    assert "personalfinance" in subs


# ── Warmup Engine ──


def test_warmup_phase_seed():
    from packages.scoring.warmup_engine import determine_warmup_phase

    now = datetime.now(timezone.utc)
    created = now - timedelta(days=1)
    phase = determine_warmup_phase(created, now)
    assert phase["phase"] == "seed"
    assert phase["max_posts_per_day"] == 0
    assert phase["monetization_allowed"] is False


def test_warmup_phase_trickle():
    from packages.scoring.warmup_engine import determine_warmup_phase

    now = datetime.now(timezone.utc)
    created = now - timedelta(days=7)
    phase = determine_warmup_phase(created, now)
    assert phase["phase"] == "trickle"
    assert phase["max_posts_per_day"] == 1


def test_warmup_phase_build():
    from packages.scoring.warmup_engine import determine_warmup_phase

    now = datetime.now(timezone.utc)
    created = now - timedelta(days=20)
    phase = determine_warmup_phase(created, now)
    assert phase["phase"] == "build"
    assert phase["max_posts_per_day"] == 2
    assert phase["monetization_allowed"] is True


def test_warmup_phase_scale():
    from packages.scoring.warmup_engine import determine_warmup_phase

    now = datetime.now(timezone.utc)
    created = now - timedelta(days=90)
    phase = determine_warmup_phase(created, now)
    assert phase["phase"] == "scale"
    assert phase["max_posts_per_day"] == 10


def test_can_post_within_limit():
    from packages.scoring.warmup_engine import can_post_now

    now = datetime.now(timezone.utc)
    created = now - timedelta(days=20)
    result = can_post_now(created, "instagram", 1, now)
    assert result["allowed"] is True


def test_cannot_post_over_limit():
    from packages.scoring.warmup_engine import can_post_now

    now = datetime.now(timezone.utc)
    created = now - timedelta(days=7)
    result = can_post_now(created, "tiktok", 1, now)
    assert result["allowed"] is False


def test_can_monetize_after_build():
    from packages.scoring.warmup_engine import can_monetize

    now = datetime.now(timezone.utc)
    assert can_monetize(now - timedelta(days=20), now) is True
    assert can_monetize(now - timedelta(days=5), now) is False


def test_shadow_ban_detection():
    from packages.scoring.warmup_engine import detect_shadow_ban

    metrics = [{"impressions": 1000}] * 5 + [{"impressions": 50}] * 5
    result = detect_shadow_ban(metrics, baseline_impressions=1000)
    assert result["detected"] is True


def test_shadow_ban_zero_reach():
    from packages.scoring.warmup_engine import detect_shadow_ban

    metrics = [{"impressions": 500}] * 3 + [{"impressions": 0}, {"impressions": 0}, {"impressions": 0}]
    result = detect_shadow_ban(metrics)
    assert result["detected"] is True
    assert result["severity"] == "critical"


def test_no_shadow_ban_healthy():
    from packages.scoring.warmup_engine import detect_shadow_ban

    metrics = [{"impressions": 500}] * 10
    result = detect_shadow_ban(metrics)
    assert result["detected"] is False


def test_cooldown_plan():
    from packages.scoring.warmup_engine import generate_cooldown_plan

    plan = generate_cooldown_plan("critical")
    assert plan["pause_days"] == 7
    assert plan["monetization_pause"] is True


# ── Voice Profile Engine ──


def test_voice_profile_generation():
    from packages.scoring.voice_profile_engine import generate_voice_profile

    profile = generate_voice_profile("acct-123", "youtube", "personal_finance")
    assert profile["style"] in [
        "conversational_direct",
        "storyteller_narrative",
        "data_driven_analytical",
        "provocative_contrarian",
        "empathetic_supportive",
        "high_energy_motivational",
        "dry_witty_humor",
        "academic_authoritative",
        "street_smart_practical",
        "minimalist_punchy",
    ]
    assert profile["vocabulary_level"] in ["casual", "accessible", "professional", "technical", "elite"]
    assert len(profile["signature_phrases"]) > 0


def test_voice_profile_deterministic():
    from packages.scoring.voice_profile_engine import generate_voice_profile

    p1 = generate_voice_profile("acct-abc", "tiktok", "fitness")
    p2 = generate_voice_profile("acct-abc", "tiktok", "fitness")
    assert p1["style"] == p2["style"]
    assert p1["signature_phrases"] == p2["signature_phrases"]


def test_voice_profiles_unique():
    from packages.scoring.voice_profile_engine import generate_voice_profile

    p1 = generate_voice_profile("acct-001", "youtube", "finance")
    p2 = generate_voice_profile("acct-002", "youtube", "finance")
    assert p1["style"] != p2["style"] or p1["signature_phrases"] != p2["signature_phrases"]


def test_voice_prompt_injection():
    from packages.scoring.voice_profile_engine import build_voice_prompt_injection, generate_voice_profile

    profile = generate_voice_profile("acct-xyz", "instagram", "beauty")
    injection = build_voice_prompt_injection(profile)
    assert "VOICE STYLE:" in injection
    assert "VOCABULARY:" in injection


# ── Content Generation Service ──


def test_parse_script_output():
    from apps.api.services.content_generation_service import _parse_script_output

    text = "[HOOK]\nBig opening\n\n[BODY]\nMain content here\n\n[CTA]\nCheck the link"
    hook, body, cta = _parse_script_output(text)
    assert "Big opening" in hook
    assert "Main content" in body
    assert "Check the link" in cta


def test_parse_script_no_markers():
    from apps.api.services.content_generation_service import _parse_script_output

    text = "Just a plain text response without markers"
    hook, body, cta = _parse_script_output(text)
    assert body == text
    assert hook == ""


def test_estimate_duration():
    from apps.api.services.content_generation_service import _estimate_duration

    short_text = " ".join(["word"] * 75)
    assert _estimate_duration(short_text) == 30
    long_text = " ".join(["word"] * 375)
    assert _estimate_duration(long_text) == 150


def test_build_generation_prompt():
    from unittest.mock import MagicMock

    from apps.api.services.content_generation_service import _build_generation_prompt

    brief = MagicMock()
    brief.title = "Test Topic"
    brief.target_platform = "youtube"
    brief.content_type = MagicMock(value="SHORT_VIDEO")
    brief.hook = "Bold opening"
    brief.angle = "Data-driven"
    brief.key_points = ["Point 1", "Point 2"]
    brief.tone_guidance = "Engaging"
    brief.target_duration_seconds = 60
    brief.cta_strategy = "Check the link"
    brief.monetization_integration = "affiliate"

    prompt = _build_generation_prompt(
        brief,
        None,
        {
            "winning_patterns": [{"pattern_name": "curiosity_gap", "pattern_type": "hook", "win_score": 0.85}],
            "losing_patterns": [{"pattern_name": "generic_intro", "pattern_type": "hook"}],
        },
    )
    assert "Test Topic" in prompt
    assert "curiosity_gap" in prompt
    assert "generic_intro" in prompt
    assert "youtube" in prompt.lower()


# ── Trend Data Clients ──


def test_trend_clients_importable():
    from packages.clients.trend_data_clients import (
        GoogleTrendsClient,
        RedditTrendingClient,
        YouTubeTrendingClient,
    )

    assert YouTubeTrendingClient is not None
    assert GoogleTrendsClient is not None
    assert RedditTrendingClient is not None


def test_claude_content_client_importable():
    from packages.clients.ai_clients import ClaudeContentClient

    c = ClaudeContentClient()
    assert not c._is_configured()


# ── Platform Content Type Mapping ──


def test_platform_content_types():
    from workers.content_ideation_worker.tasks import PLATFORM_CONTENT_TYPES

    assert "youtube" in PLATFORM_CONTENT_TYPES
    assert "tiktok" in PLATFORM_CONTENT_TYPES
    assert len(PLATFORM_CONTENT_TYPES["youtube"]) >= 1
