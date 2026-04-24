"""Hashtag Optimization Engine — score and select hashtags from trend data + niche keywords."""
from __future__ import annotations

PLATFORM_HASHTAG_LIMITS = {
    "instagram": 10, "tiktok": 8, "youtube": 5, "x": 3, "linkedin": 5, "reddit": 0, "pinterest": 5,
}

EVERGREEN_HASHTAGS: dict[str, list[str]] = {
    "personal_finance": ["#money", "#finance", "#investing", "#budgeting", "#wealth", "#savings", "#financialfreedom"],
    "make_money_online": ["#sidehustle", "#passiveincome", "#makemoney", "#onlinebusiness", "#entrepreneur"],
    "health_fitness": ["#fitness", "#workout", "#health", "#nutrition", "#weightloss", "#gym"],
    "tech_reviews": ["#tech", "#gadgets", "#review", "#technology", "#apps"],
    "ai_tools": ["#AI", "#ChatGPT", "#artificial intelligence", "#automation", "#productivity"],
    "crypto": ["#crypto", "#bitcoin", "#blockchain", "#defi", "#web3"],
    "real_estate": ["#realestate", "#property", "#investing", "#mortgage", "#realtips"],
    "self_improvement": ["#selfimprovement", "#productivity", "#mindset", "#growth", "#habits"],
    "business_entrepreneurship": ["#business", "#entrepreneur", "#startup", "#marketing", "#growth"],
    "beauty_skincare": ["#skincare", "#beauty", "#makeup", "#selfcare", "#routine"],
}

PLATFORM_MANDATORY = {
    "tiktok": ["#fyp", "#foryou"],
    "instagram": [],
    "youtube": [],
    "x": [],
    "linkedin": [],
}


def score_hashtag(hashtag: str, niche: str, trending_hashtags: list[str] | None = None) -> float:
    """Score a hashtag 0-1 based on relevance and trendiness."""
    score = 0.3
    niche_tags = EVERGREEN_HASHTAGS.get(niche, [])
    if hashtag.lower() in [t.lower() for t in niche_tags]:
        score += 0.4
    if trending_hashtags and hashtag.lower() in [t.lower() for t in trending_hashtags]:
        score += 0.3
    return min(1.0, score)


def select_optimal_hashtags(
    niche: str,
    platform: str,
    topic_keywords: list[str] | None = None,
    trending_hashtags: list[str] | None = None,
) -> list[str]:
    """Select the best hashtags for a post given niche, platform, and trend data."""
    limit = PLATFORM_HASHTAG_LIMITS.get(platform.lower(), 5)
    if limit == 0:
        return []

    mandatory = PLATFORM_MANDATORY.get(platform.lower(), [])
    candidates: list[tuple[str, float]] = []

    for tag in mandatory:
        candidates.append((tag, 1.0))

    niche_tags = EVERGREEN_HASHTAGS.get(niche, [])
    for tag in niche_tags:
        candidates.append((tag, score_hashtag(tag, niche, trending_hashtags)))

    if topic_keywords:
        for kw in topic_keywords:
            tag = f"#{kw.replace(' ', '').lower()}"
            if tag not in [c[0] for c in candidates]:
                candidates.append((tag, score_hashtag(tag, niche, trending_hashtags)))

    if trending_hashtags:
        for tag in trending_hashtags[:10]:
            formatted = tag if tag.startswith("#") else f"#{tag}"
            if formatted not in [c[0] for c in candidates]:
                candidates.append((formatted, 0.7))

    candidates.sort(key=lambda x: x[1], reverse=True)
    seen = set()
    selected = []
    for tag, _ in candidates:
        if tag.lower() not in seen and len(selected) < limit:
            seen.add(tag.lower())
            selected.append(tag)

    return selected


def build_hashtag_prompt_section(hashtags: list[str], platform: str) -> str:
    """Build a prompt injection section for hashtag guidance."""
    if not hashtags:
        return ""
    return f"USE THESE HASHTAGS (in order of priority): {' '.join(hashtags)}"
