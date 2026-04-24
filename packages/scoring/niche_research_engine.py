"""Niche Research Engine — score niches by monetization potential, competition, trend velocity."""
from __future__ import annotations

from typing import Any

NICHE_DATABASE: list[dict[str, Any]] = [
    {"niche": "personal_finance", "keywords": ["budgeting", "investing", "saving", "credit", "debt", "wealth"], "youtube_cpm_range": (8, 25), "affiliate_density": 0.9, "competition": 0.8, "evergreen": True},
    {"niche": "make_money_online", "keywords": ["side hustle", "passive income", "freelancing", "dropshipping", "affiliate"], "youtube_cpm_range": (10, 30), "affiliate_density": 0.95, "competition": 0.9, "evergreen": True},
    {"niche": "health_fitness", "keywords": ["workout", "diet", "weight loss", "muscle", "nutrition", "supplements"], "youtube_cpm_range": (5, 15), "affiliate_density": 0.8, "competition": 0.7, "evergreen": True},
    {"niche": "tech_reviews", "keywords": ["gadgets", "phones", "laptops", "software", "apps", "AI tools"], "youtube_cpm_range": (6, 20), "affiliate_density": 0.85, "competition": 0.75, "evergreen": False},
    {"niche": "ai_tools", "keywords": ["ChatGPT", "AI", "automation", "productivity", "tools", "prompts"], "youtube_cpm_range": (8, 25), "affiliate_density": 0.9, "competition": 0.6, "evergreen": False},
    {"niche": "crypto", "keywords": ["bitcoin", "crypto", "blockchain", "defi", "trading", "web3"], "youtube_cpm_range": (10, 35), "affiliate_density": 0.85, "competition": 0.85, "evergreen": False},
    {"niche": "real_estate", "keywords": ["property", "rental", "mortgage", "flipping", "REITs", "investing"], "youtube_cpm_range": (12, 30), "affiliate_density": 0.75, "competition": 0.65, "evergreen": True},
    {"niche": "self_improvement", "keywords": ["productivity", "habits", "mindset", "motivation", "discipline"], "youtube_cpm_range": (4, 12), "affiliate_density": 0.6, "competition": 0.5, "evergreen": True},
    {"niche": "business_entrepreneurship", "keywords": ["startup", "business", "marketing", "sales", "growth"], "youtube_cpm_range": (8, 25), "affiliate_density": 0.8, "competition": 0.7, "evergreen": True},
    {"niche": "cooking_recipes", "keywords": ["recipe", "cooking", "meal prep", "kitchen", "food"], "youtube_cpm_range": (3, 10), "affiliate_density": 0.7, "competition": 0.5, "evergreen": True},
    {"niche": "gaming", "keywords": ["gaming", "game", "playthrough", "tips", "esports"], "youtube_cpm_range": (2, 8), "affiliate_density": 0.65, "competition": 0.9, "evergreen": False},
    {"niche": "beauty_skincare", "keywords": ["skincare", "makeup", "beauty", "routine", "products"], "youtube_cpm_range": (5, 18), "affiliate_density": 0.85, "competition": 0.7, "evergreen": True},
    {"niche": "travel", "keywords": ["travel", "destination", "budget travel", "adventure", "digital nomad"], "youtube_cpm_range": (4, 15), "affiliate_density": 0.75, "competition": 0.6, "evergreen": True},
    {"niche": "education_courses", "keywords": ["learn", "course", "tutorial", "certification", "skills"], "youtube_cpm_range": (8, 22), "affiliate_density": 0.8, "competition": 0.55, "evergreen": True},
    {"niche": "software_saas", "keywords": ["SaaS", "software", "tools", "review", "comparison", "tutorial"], "youtube_cpm_range": (10, 30), "affiliate_density": 0.9, "competition": 0.65, "evergreen": True},
]

PLATFORM_MULTIPLIERS = {
    "youtube": {"cpm_weight": 1.0, "long_form_fit": 1.0, "short_form_fit": 0.7, "monetization_maturity": 1.0},
    "tiktok": {"cpm_weight": 0.3, "long_form_fit": 0.2, "short_form_fit": 1.0, "monetization_maturity": 0.5},
    "instagram": {"cpm_weight": 0.4, "long_form_fit": 0.3, "short_form_fit": 0.9, "monetization_maturity": 0.7},
    "x": {"cpm_weight": 0.2, "long_form_fit": 0.1, "short_form_fit": 0.8, "monetization_maturity": 0.3},
    "linkedin": {"cpm_weight": 0.5, "long_form_fit": 0.6, "short_form_fit": 0.5, "monetization_maturity": 0.4},
}


def score_niche(niche: dict[str, Any], platform: str = "youtube", trend_signals: list[dict] | None = None) -> dict[str, Any]:
    """Score a niche for a specific platform."""
    plat = PLATFORM_MULTIPLIERS.get(platform, PLATFORM_MULTIPLIERS["youtube"])

    cpm_low, cpm_high = niche.get("youtube_cpm_range", (5, 15))
    avg_cpm = (cpm_low + cpm_high) / 2
    cpm_score = min(1.0, avg_cpm / 30) * plat["cpm_weight"]

    affiliate_score = niche.get("affiliate_density", 0.5)
    competition_penalty = niche.get("competition", 0.5) * 0.3
    evergreen_bonus = 0.1 if niche.get("evergreen") else 0

    trend_velocity = 0.0
    if trend_signals:
        niche_keywords = set(k.lower() for k in niche.get("keywords", []))
        matches = sum(1 for t in trend_signals if any(kw in t.get("title", "").lower() for kw in niche_keywords))
        trend_velocity = min(0.3, matches * 0.05)

    monetization_score = (cpm_score * 0.3 + affiliate_score * 0.3) * plat["monetization_maturity"]
    opportunity_score = (1.0 - competition_penalty) + trend_velocity + evergreen_bonus

    composite = monetization_score * 0.5 + opportunity_score * 0.5

    return {
        "niche": niche["niche"],
        "platform": platform,
        "composite_score": round(composite, 4),
        "monetization_score": round(monetization_score, 4),
        "opportunity_score": round(opportunity_score, 4),
        "cpm_score": round(cpm_score, 4),
        "affiliate_density": niche.get("affiliate_density", 0),
        "competition": niche.get("competition", 0),
        "trend_velocity": round(trend_velocity, 4),
        "evergreen": niche.get("evergreen", False),
        "avg_cpm": avg_cpm,
        "keywords": niche.get("keywords", []),
    }


def rank_niches(platforms: list[str] | None = None, trend_signals: list[dict] | None = None, top_n: int = 10) -> list[dict[str, Any]]:
    """Rank all niches across platforms, return top N."""
    platforms = platforms or ["youtube", "tiktok", "instagram", "x", "linkedin"]
    all_scores = []
    for niche in NICHE_DATABASE:
        for platform in platforms:
            all_scores.append(score_niche(niche, platform, trend_signals))
    all_scores.sort(key=lambda x: x["composite_score"], reverse=True)
    return all_scores[:top_n]


def recommend_initial_niches(num_niches: int = 5) -> list[dict[str, Any]]:
    """Recommend the best starting niches for a new content farm."""
    ranked = rank_niches(top_n=50)
    selected = []
    seen_niches = set()
    for r in ranked:
        if r["niche"] not in seen_niches and len(selected) < num_niches:
            seen_niches.add(r["niche"])
            selected.append(r)
    return selected


def get_niche_subreddits(niche: str) -> list[str]:
    """Return relevant subreddits for monitoring a niche."""
    mapping = {
        "personal_finance": ["personalfinance", "financialindependence", "investing", "frugal"],
        "make_money_online": ["beermoney", "WorkOnline", "passive_income", "Entrepreneur"],
        "health_fitness": ["fitness", "loseit", "bodybuilding", "nutrition"],
        "tech_reviews": ["technology", "gadgets", "Android", "apple"],
        "ai_tools": ["artificial", "ChatGPT", "LocalLLaMA", "singularity"],
        "crypto": ["CryptoCurrency", "Bitcoin", "defi", "ethtrader"],
        "real_estate": ["realestateinvesting", "RealEstate", "landlords"],
        "self_improvement": ["selfimprovement", "productivity", "getdisciplined"],
        "business_entrepreneurship": ["Entrepreneur", "startups", "smallbusiness"],
        "software_saas": ["SaaS", "webdev", "programming"],
    }
    return mapping.get(niche, ["popular"])


NICHE_AFFILIATE_MAP: dict[str, list[str]] = {
    "personal_finance": ["clickbank", "semrush", "shareasale", "impact", "amazon"],
    "make_money_online": ["clickbank", "semrush", "wpx", "shareasale", "amazon"],
    "health_fitness": ["clickbank", "tiktok_shopping", "amazon", "target", "shareasale", "spotify"],
    "tech_reviews": ["amazon", "youtube_shopping", "semrush", "target", "impact"],
    "ai_tools": ["semrush", "wpx", "clickbank", "shareasale", "amazon"],
    "crypto": ["clickbank", "impact", "amazon"],
    "real_estate": ["clickbank", "amazon", "semrush", "impact"],
    "self_improvement": ["clickbank", "tiktok_shopping", "amazon", "spotify", "etsy"],
    "business_entrepreneurship": ["semrush", "wpx", "clickbank", "shareasale", "impact"],
    "cooking_recipes": ["amazon", "target", "youtube_shopping", "tiktok_shopping", "etsy"],
    "gaming": ["amazon", "youtube_shopping", "target"],
    "beauty_skincare": ["tiktok_shopping", "amazon", "target", "etsy", "youtube_shopping", "shareasale"],
    "travel": ["amazon", "spotify", "target", "impact", "etsy"],
    "education_courses": ["clickbank", "semrush", "shareasale", "amazon"],
    "software_saas": ["semrush", "wpx", "impact", "clickbank", "shareasale"],
}


def get_affiliate_programs_for_niche(niche: str) -> list[str]:
    """Return ranked affiliate program keys for a niche."""
    return NICHE_AFFILIATE_MAP.get(niche, ["amazon", "clickbank"])
