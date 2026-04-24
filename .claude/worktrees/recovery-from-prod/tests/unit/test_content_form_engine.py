"""Unit tests for Content Form Selection + Mix Allocation engine."""
from __future__ import annotations

import pytest

from packages.scoring.content_form_engine import (
    AVATAR_MODES,
    CONTENT_FORMS,
    FORMAT_FAMILIES,
    FUNNEL_STAGE_FIT,
    PLATFORM_FIT,
    _score_form,
    compute_mix_reports,
    detect_content_form_blockers,
    recommend_content_forms,
)


def test_constants_are_consistent():
    for form in CONTENT_FORMS:
        assert form in FORMAT_FAMILIES
        assert form in AVATAR_MODES


def test_recommend_returns_list():
    out = recommend_content_forms(platform="youtube")
    assert isinstance(out, list)
    assert len(out) > 0


def test_recommend_has_required_fields():
    out = recommend_content_forms(platform="youtube")
    required = (
        "recommended_content_form",
        "format_family",
        "short_or_long",
        "avatar_mode",
        "confidence",
        "explanation",
    )
    for row in out:
        for key in required:
            assert key in row, f"missing {key}"


def test_avatar_mode_none_when_no_avatar():
    out = recommend_content_forms(platform="youtube", has_avatar=False)
    top = out[0]
    if top["recommended_content_form"] == "avatar_led_video":
        assert top["blockers"], "avatar-led top pick should carry avatar blockers when has_avatar=False"


def test_avatar_led_ranks_higher_with_avatar():
    low = _score_form(
        "avatar_led_video", "youtube", "affiliate", "awareness",
        0.0, 0.0, False, True, "new", "low",
    )
    high = _score_form(
        "avatar_led_video", "youtube", "affiliate", "awareness",
        0.0, 0.0, True, True, "new", "low",
    )
    assert high > low


def test_faceless_ranks_high_on_tiktok():
    out = recommend_content_forms(platform="tiktok")
    top3 = [r["recommended_content_form"] for r in out[:3]]
    assert "faceless_short_form" in top3


def test_text_led_ranks_high_on_twitter():
    out = recommend_content_forms(platform="twitter")
    top3 = [r["recommended_content_form"] for r in out[:3]]
    assert "text_led_post" in top3


def test_long_form_ranks_high_on_youtube():
    out = recommend_content_forms(
        platform="youtube",
        monetization="sponsorship",
        funnel_stage="consideration",
        account_maturity="mature",
    )
    top3 = [r["recommended_content_form"] for r in out[:3]]
    assert "long_form_video" in top3


def test_proof_ranks_high_for_conversion():
    # Reddit lists proof early in PLATFORM_FIT; conversion + digital_product lift it into the top 3.
    out = recommend_content_forms(
        platform="reddit",
        funnel_stage="conversion",
        monetization="digital_product",
        account_maturity="mature",
    )
    top3 = [r["recommended_content_form"] for r in out[:3]]
    assert "proof_testimonial" in top3


def test_low_cost_for_new_accounts():
    out = recommend_content_forms(platform="youtube", account_maturity="new")
    assert out[0]["production_cost_band"] in ("low", "medium")


def test_high_trust_boosts_proof():
    out = recommend_content_forms(
        platform="youtube",
        trust_need="high",
        monetization="digital_product",
        funnel_stage="conversion",
        account_maturity="mature",
    )
    top3 = [r["recommended_content_form"] for r in out[:3]]
    assert "proof_testimonial" in top3 or "founder_expert" in top3


def test_saturation_boosts_expansion_forms():
    low_sat = _score_form(
        "faceless_short_form", "youtube", "affiliate", "awareness",
        0.0, 0.0, True, True, "mature", "low",
    )
    high_sat = _score_form(
        "faceless_short_form", "youtube", "affiliate", "awareness",
        0.75, 0.0, True, True, "mature", "low",
    )
    assert high_sat >= low_sat + 0.09


def test_fatigue_penalizes_heavy_forms():
    calm = _score_form(
        "avatar_led_video", "youtube", "sponsorship", "awareness",
        0.0, 0.0, True, True, "mature", "low",
    )
    tired = _score_form(
        "avatar_led_video", "youtube", "sponsorship", "awareness",
        0.0, 0.7, True, True, "mature", "low",
    )
    assert tired < calm

    lf_calm = _score_form(
        "long_form_video", "youtube", "sponsorship", "consideration",
        0.0, 0.0, True, True, "mature", "low",
    )
    lf_tired = _score_form(
        "long_form_video", "youtube", "sponsorship", "consideration",
        0.0, 0.7, True, True, "mature", "low",
    )
    assert lf_tired < lf_calm


def test_confidence_in_range():
    out = recommend_content_forms(platform="instagram")
    for row in out:
        assert 0.0 <= row["confidence"] <= 1.0


def test_secondary_form_present():
    out = recommend_content_forms(platform="linkedin")
    assert out[0]["secondary_content_form"] is not None


def test_mix_reports_not_empty():
    recs = recommend_content_forms(platform="youtube")
    reports = compute_mix_reports(recs)
    assert len(reports) >= 1


def test_mix_has_platform_dimension():
    recs = recommend_content_forms(platform="youtube")
    reports = compute_mix_reports(recs)
    assert any(r["dimension"] == "platform" for r in reports)


def test_mix_has_funnel_dimension():
    recs = recommend_content_forms(platform="youtube")
    reports = compute_mix_reports(recs)
    assert any(r["dimension"] == "funnel_stage" for r in reports)


def test_mix_allocation_sums_close_to_one():
    recs = recommend_content_forms(platform="tiktok")
    reports = compute_mix_reports(recs)
    plat = next(r for r in reports if r["dimension"] == "platform")
    total = sum(plat["mix_allocation"].values())
    assert abs(total - 1.0) < 0.02


def test_blockers_no_avatar():
    b = detect_content_form_blockers(False, True, 5, 2)
    types = {x["blocker_type"] for x in b}
    assert "no_avatar_provider" in types


def test_blockers_no_voice():
    b = detect_content_form_blockers(True, False, 5, 2)
    types = {x["blocker_type"] for x in b}
    assert "no_voice_provider" in types


def test_blockers_no_content():
    b = detect_content_form_blockers(True, True, 0, 2)
    assert any(x["blocker_type"] == "no_content_history" for x in b)


def test_blockers_no_offers():
    b = detect_content_form_blockers(True, True, 10, 0)
    assert any(x["blocker_type"] == "no_offers" for x in b)


def test_no_blockers_when_all_present():
    b = detect_content_form_blockers(True, True, 10, 3)
    assert b == []


def test_platform_fit_covers_major_platforms():
    for p in ("youtube", "tiktok", "twitter", "instagram"):
        assert p in PLATFORM_FIT
        assert len(PLATFORM_FIT[p]) >= 1


def test_funnel_stage_fit_has_core_stages():
    for stage in ("awareness", "consideration", "conversion", "retention"):
        assert stage in FUNNEL_STAGE_FIT
