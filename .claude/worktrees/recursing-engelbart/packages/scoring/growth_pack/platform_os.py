"""Explicit platform operating logic — deterministic, explainable (no fake ML).

Supported platforms: tiktok, instagram, youtube, twitter (X), reddit, linkedin, facebook.
"""
from __future__ import annotations
from typing import Any

PLATFORM_SPECS: dict[str, dict[str, Any]] = {
    "tiktok": {
        "recommended_roles": ["trend_capture", "viral_satellite", "short_offer_cta"],
        "posting_cadence_posts_per_week": {"min": 7, "max": 28},
        "monetization_styles": ["affiliate_bio_link", "spark_ads", "creator_fund", "lead_gen_comment_funnel"],
        "audience_development": "hook_first_3s_sound_trending_hashtag_niche_stitch",
        "time_to_signal_days_range": {"min": 3, "max": 14},
        "expansion_conditions": ["avg_completion_rate_above_50pct", "share_rate_rising", "profile_view_rate_above_1pct"],
        "saturation_indicators": ["sound_fatigue", "hook_format_repetition", "cpm_spike_no_engagement_lift"],
        "warmup_cadence": {
            "week_1": 1,
            "week_2": 2,
            "week_3_4": 3,
            "steady_state_min": 7,
            "steady_state_max": 21,
        },
        "ramp_behavior": "aggressive_if_completion_rate_above_40pct_else_slow",
        "scale_ready_conditions": [
            "at_least_10_posts_published",
            "avg_completion_rate_above_40pct",
            "follower_velocity_positive_7d",
            "no_community_guideline_strikes",
        ],
        "max_safe_output_per_day": 4,
        "spam_fatigue_signals": ["shadow_ban_indicator_zero_fyp", "completion_rate_collapse_below_20pct", "report_rate_above_threshold"],
        "account_health_signals": ["community_guideline_strikes", "monetization_eligibility_status", "appeal_pending"],
        "derivative_style_guidance": "Repurpose long-form → sub-60s clips with text overlay hooks; stitch/duet for engagement amplification",
    },
    "instagram": {
        "recommended_roles": ["flagship_visual", "reels_satellite", "story_cta_test"],
        "posting_cadence_posts_per_week": {"min": 5, "max": 21},
        "monetization_styles": ["affiliate_shoppable", "sponsored_reels", "lead_gen_bio"],
        "audience_development": "visual_consistency_hashtag_clusters_dm_funnels",
        "time_to_signal_days_range": {"min": 7, "max": 21},
        "expansion_conditions": ["reels_ctr_above_2pct", "save_rate_rising", "fatigue_below_0.45"],
        "saturation_indicators": ["audience_overlap_with_sister_ig", "reel_sound_fatigue", "cpm_rising"],
        "warmup_cadence": {
            "week_1": 2,
            "week_2": 3,
            "week_3_4": 5,
            "steady_state_min": 5,
            "steady_state_max": 14,
        },
        "ramp_behavior": "moderate_visual_consistency_first",
        "scale_ready_conditions": [
            "at_least_14_posts_published",
            "reels_reach_stable",
            "save_rate_above_2pct",
        ],
        "max_safe_output_per_day": 3,
        "spam_fatigue_signals": ["action_block_triggered", "reach_collapse", "unfollow_spike"],
        "account_health_signals": ["action_blocks", "content_violations", "appeal_status"],
        "derivative_style_guidance": "Carousel from listicle; Reels from short video; Story polls for engagement",
    },
    "youtube": {
        "recommended_roles": ["evergreen_authority", "shorts_experiment", "longform_offer"],
        "posting_cadence_posts_per_week": {"min": 2, "max": 7},
        "monetization_styles": ["adsense", "affiliate_description", "sponsor_integrations", "digital_products"],
        "audience_development": "search_intent_clusters_playlist_funnels",
        "time_to_signal_days_range": {"min": 14, "max": 45},
        "expansion_conditions": ["avg_view_duration_rising", "ctr_stable", "subs_velocity_positive"],
        "saturation_indicators": ["same_title_patterns_as_sister_channel", "rpm_stagnant", "audience_overlap"],
        "warmup_cadence": {
            "week_1": 1,
            "week_2": 2,
            "week_3_4": 3,
            "steady_state_min": 2,
            "steady_state_max": 7,
        },
        "ramp_behavior": "slow_seo_authority_building",
        "scale_ready_conditions": [
            "at_least_8_videos_published",
            "avg_view_duration_above_40pct",
            "ctr_above_4pct",
        ],
        "max_safe_output_per_day": 2,
        "spam_fatigue_signals": ["ctr_collapse", "dislike_ratio_spike", "unsub_velocity"],
        "account_health_signals": ["community_strikes", "monetization_status", "copyright_claims"],
        "derivative_style_guidance": "Shorts from longform highlights; Community posts for engagement; Playlist funnel",
    },
    "twitter": {
        "recommended_roles": ["thought_leadership", "reply_growth", "thread_conversion"],
        "posting_cadence_posts_per_week": {"min": 7, "max": 35},
        "monetization_styles": ["newsletter_funnel", "sponsored_posts", "affiliate_short_links"],
        "audience_development": "reply_velocity_lists_communities",
        "time_to_signal_days_range": {"min": 3, "max": 14},
        "expansion_conditions": ["profile_ctr_above_1pct", "follower_velocity_positive"],
        "saturation_indicators": ["topic_overlap_threads", "engagement_rate_decline"],
        "warmup_cadence": {
            "week_1": 3,
            "week_2": 5,
            "week_3_4": 7,
            "steady_state_min": 7,
            "steady_state_max": 28,
        },
        "ramp_behavior": "fast_reply_first_then_original",
        "scale_ready_conditions": [
            "at_least_50_posts",
            "reply_engagement_rate_above_1pct",
            "follower_velocity_positive_14d",
        ],
        "max_safe_output_per_day": 10,
        "spam_fatigue_signals": ["rate_limit_hits", "engagement_collapse", "report_waves"],
        "account_health_signals": ["suspension_warnings", "restricted_features", "appeal_pending"],
        "derivative_style_guidance": "Thread from longform; Quote-tweet hooks; Polls for engagement",
    },
    "reddit": {
        "recommended_roles": ["community_value", "ama_style", "resource_posts"],
        "posting_cadence_posts_per_week": {"min": 2, "max": 10},
        "monetization_styles": ["soft_affiliate", "owned_list_funnel", "digital_product_pm"],
        "audience_development": "subreddit_rules_first_karma_building",
        "time_to_signal_days_range": {"min": 14, "max": 60},
        "expansion_conditions": ["karma_threshold_met", "mod_approval_stable"],
        "saturation_indicators": ["ban_risk_overlap", "subreddit_saturation_same_niche"],
        "warmup_cadence": {
            "week_1": 1,
            "week_2": 2,
            "week_3_4": 3,
            "steady_state_min": 2,
            "steady_state_max": 7,
        },
        "ramp_behavior": "slow_karma_build_comment_first",
        "scale_ready_conditions": [
            "karma_above_500",
            "no_bans_or_warnings",
            "positive_post_ratio_above_80pct",
        ],
        "max_safe_output_per_day": 3,
        "spam_fatigue_signals": ["mod_removal_spike", "downvote_ratio_above_50pct", "shadowban_indicator"],
        "account_health_signals": ["subreddit_bans", "admin_warnings", "karma_trajectory"],
        "derivative_style_guidance": "Long-form value posts; AMAs from expertise; Resource compilations from content",
    },
    "linkedin": {
        "recommended_roles": ["executive_authority", "newsletter_drip", "case_study"],
        "posting_cadence_posts_per_week": {"min": 3, "max": 10},
        "monetization_styles": ["b2b_leads", "high_ticket_calls", "sponsored_newsletter"],
        "audience_development": "network_expansion_comment_led",
        "time_to_signal_days_range": {"min": 14, "max": 30},
        "expansion_conditions": ["ssi_rising", "inbound_dm_rate_stable"],
        "saturation_indicators": ["same_icp_overlap_accounts", "connection_fatigue"],
        "warmup_cadence": {
            "week_1": 2,
            "week_2": 3,
            "week_3_4": 4,
            "steady_state_min": 3,
            "steady_state_max": 7,
        },
        "ramp_behavior": "moderate_network_seeding_first",
        "scale_ready_conditions": [
            "at_least_10_posts",
            "ssi_above_50",
            "engagement_rate_above_2pct",
        ],
        "max_safe_output_per_day": 2,
        "spam_fatigue_signals": ["connection_acceptance_collapse", "unfollow_spike", "content_restriction"],
        "account_health_signals": ["account_restrictions", "content_violations", "ssi_trend"],
        "derivative_style_guidance": "Carousel from blog posts; Newsletter from longform; Polls for B2B engagement",
    },
    "facebook": {
        "recommended_roles": ["group_engine", "reels_test", "local_lead_gen"],
        "posting_cadence_posts_per_week": {"min": 3, "max": 14},
        "monetization_styles": ["group_affiliate", "local_services", "ad_arbitrage"],
        "audience_development": "group_seeding_events_retargeting",
        "time_to_signal_days_range": {"min": 7, "max": 28},
        "expansion_conditions": ["group_growth_rate_positive", "repeat_engagement"],
        "saturation_indicators": ["audience_overlap_pages", "cpm_volatility"],
        "warmup_cadence": {
            "week_1": 2,
            "week_2": 3,
            "week_3_4": 5,
            "steady_state_min": 3,
            "steady_state_max": 10,
        },
        "ramp_behavior": "moderate_group_seeding_first",
        "scale_ready_conditions": [
            "group_or_page_above_500_members",
            "repeat_engagement_rate_above_3pct",
        ],
        "max_safe_output_per_day": 3,
        "spam_fatigue_signals": ["reach_collapse_organic", "group_member_churn", "content_restriction"],
        "account_health_signals": ["page_restrictions", "ad_account_status", "content_violations"],
        "derivative_style_guidance": "Reels from short video; Group posts from blog content; Events from webinars",
    },
}

ALL_SUPPORTED_PLATFORMS = list(PLATFORM_SPECS.keys())


def normalize_platform(p: str | None) -> str:
    if not p:
        return "youtube"
    x = p.lower().strip()
    if x in ("x", "twitter"):
        return "twitter"
    return x if x in PLATFORM_SPECS else "youtube"


def platform_spec(platform: str) -> dict[str, Any]:
    return PLATFORM_SPECS.get(normalize_platform(platform), PLATFORM_SPECS["youtube"])
