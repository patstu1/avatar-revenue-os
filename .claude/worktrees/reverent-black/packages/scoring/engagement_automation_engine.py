"""Engagement Automation Engine — generate contextual engagement actions for warmup accounts.

During seed/trickle phases, accounts need to engage with niche content to build credibility
and trigger algorithmic recognition before posting their own content.
"""
from __future__ import annotations
import random
from typing import Any

ENGAGEMENT_ACTIONS = ["like", "comment", "follow", "save"]

COMMENT_TEMPLATES: dict[str, list[str]] = {
    "personal_finance": [
        "This is such an underrated point about budgeting. More people need to see this.",
        "Great breakdown! The compound interest visual really puts it in perspective.",
        "Been doing something similar for 6 months and the results are real. Good content.",
        "This is the kind of financial advice that actually helps. Bookmarked.",
        "The part about emergency funds is so important. Thanks for sharing this.",
    ],
    "health_fitness": [
        "Finally someone explains this properly. The form tips are really helpful.",
        "I tried this routine last month and saw real improvement. Solid advice.",
        "This nutrition breakdown is exactly what I was looking for. Thank you!",
        "Great content. The progressive overload explanation is spot on.",
        "Wish I had this info when I started. Really well explained.",
    ],
    "tech_reviews": [
        "Honest review. Appreciate that you covered the downsides too.",
        "Been on the fence about this. Your comparison really helped.",
        "The battery test was the info I needed. Thanks for the detailed breakdown.",
        "Great point about the ecosystem lock-in. Not enough people talk about that.",
        "This is the most thorough review I've seen. Subscribed.",
    ],
    "ai_tools": [
        "I tested this workflow and it saves hours. Great find.",
        "The prompt engineering tips are next level. Saving this.",
        "Finally a practical AI tutorial, not just hype. Really useful.",
        "This comparison is exactly what the space needed. Well done.",
        "The automation setup is brilliant. Going to implement this today.",
    ],
    "default": [
        "Really valuable content. Thanks for putting this together.",
        "This is exactly what I needed to see today. Great work.",
        "Underrated content. More people should be watching this.",
        "Solid points throughout. Bookmarking for later.",
        "One of the better explanations I've seen on this topic.",
    ],
}


def generate_engagement_plan(
    account_phase: str,
    platform: str,
    niche: str,
) -> dict[str, Any]:
    """Generate a set of engagement actions for an account based on its warmup phase."""
    if account_phase not in ("seed", "trickle"):
        return {"actions": [], "reason": "Account past warmup engagement phase"}

    if account_phase == "seed":
        return {
            "actions": [
                {"type": "follow", "count": random.randint(3, 8), "target": f"top creators in {niche}"},
                {"type": "like", "count": random.randint(10, 20), "target": f"recent posts in {niche}"},
                {"type": "comment", "count": random.randint(2, 5), "target": f"trending content in {niche}"},
            ],
            "comments": _select_comments(niche, 5),
            "phase": "seed",
        }

    return {
        "actions": [
            {"type": "like", "count": random.randint(5, 15), "target": f"niche content in {niche}"},
            {"type": "comment", "count": random.randint(1, 3), "target": f"trending in {niche}"},
        ],
        "comments": _select_comments(niche, 3),
        "phase": "trickle",
    }


def _select_comments(niche: str, count: int) -> list[str]:
    templates = COMMENT_TEMPLATES.get(niche, COMMENT_TEMPLATES["default"])
    return random.sample(templates, min(count, len(templates)))


def generate_contextual_comment(niche: str, content_title: str = "") -> str:
    """Generate a single contextual comment for engaging with niche content."""
    templates = COMMENT_TEMPLATES.get(niche, COMMENT_TEMPLATES["default"])
    base = random.choice(templates)
    if content_title and random.random() > 0.5:
        openers = ["Love this take on", "Great point about", "This is so true about", "Needed this perspective on"]
        topic = content_title.split("—")[0].split("|")[0].strip()[:50]
        return f"{random.choice(openers)} {topic.lower()}. {base}"
    return base
